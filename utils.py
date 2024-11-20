# utils.py
import ast
import getpass
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from decimal import Decimal, getcontext
import logging
import docker
import requests
import web3.contract
from aea.crypto.base import LedgerApi
from aea_ledger_ethereum import EthereumApi
from halo import Halo
from termcolor import colored
from web3 import Web3
from web3.middleware import geth_poa_middleware
from enum import Enum
import typing as t

from operate.cli import OperateApp
from operate.resource import LocalResource, deserialize
from operate.services.manage import ServiceManager
from operate.services.protocol import EthSafeTxBuilder
from operate.services.service import Service
from operate.types import ChainType, ServiceTemplate, LedgerType, ConfigurationTemplate
from operate.utils.gnosis import SafeOperation

# Set decimal precision
getcontext().prec = 18

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')


WARNING_ICON = colored("\u26A0", "yellow")
OPERATE_HOME = Path.cwd() / ".mech_quickstart"
DEFAULT_TOOLS_TO_PACKAGE_HASH = None
DEFAULT_MECH_TO_SUBSCRIPTION = None
DEFAULT_MECH_TO_CONFIG = None
DEFAULT_MECH_HASH = "bafybeiae6wpk5vxkvgugvay237gmn6xpnk7bceahodv4xka3n2p6brqlr4"

@dataclass
class MechQuickstartConfig(LocalResource):
    """Local configuration."""

    path: Path
    gnosis_rpc: t.Optional[str] = None
    password_migrated: t.Optional[bool] = None
    use_staking: t.Optional[bool] = None
    api_keys_path: t.Optional[str] = None
    metadata_hash: t.Optional[str] = None
    agent_id: t.Optional[int] = None
    mech_address: t.Optional[str] = None
    tools_to_packages_hash: t.Optional[dict] = None
    mech_hash: t.Optional[str] = None
    home_chain_id: t.Optional[int] = None

    @classmethod
    def from_json(cls, obj: t.Dict) -> "LocalResource":
        """Load LocalResource from json."""
        kwargs = {}
        for pname, ptype in cls.__annotations__.items():
            if pname.startswith("_"):
                continue

            # allow for optional types
            is_optional_type = t.get_origin(ptype) is t.Union and type(
                None
            ) in t.get_args(ptype)
            value = obj.get(pname, None)
            if is_optional_type and value is None:
                continue

            kwargs[pname] = deserialize(obj=obj[pname], otype=ptype)
        return cls(**kwargs)


# Terminal color codes
class ColorCode:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

class StakingState(Enum):
    """Staking state enumeration for the staking."""
    UNSTAKED = 0
    STAKED = 1
    EVICTED = 2

def _color_string(text: str, color_code: str) -> str:
    return f"{color_code}{text}{ColorCode.RESET}"

def _color_bool(is_true: bool, true_string: str = "True", false_string: str = "False") -> str:
    if is_true:
        return _color_string(true_string, ColorCode.GREEN)
    return _color_string(false_string, ColorCode.RED)

def _warning_message(current_value: Decimal, threshold: Decimal, message: str = "") -> str:
    default_message = _color_string(
        f"- Value too low. Threshold is {threshold:.2f}.",
        ColorCode.YELLOW,
    )
    if current_value < threshold:
        return _color_string(message or default_message, ColorCode.YELLOW)
    return ""

def _print_section_header(header: str, output_width: int = 80) -> None:
    print("\n\n" + header)
    print("=" * output_width)

def _print_subsection_header(header: str, output_width: int = 80) -> None:
    print("\n" + header)
    print("-" * output_width)

def _print_status(key: str, value: str, message: str = "") -> None:
    line = f"{key:<30}{value:<20}"
    if message:
        line += f"{message}"
    print(line)

def wei_to_olas(wei: int) -> str:
    """Converts and formats wei to OLAS."""
    return "{:.2f} OLAS".format(wei_to_unit(wei))

def wei_to_eth(wei_value):
    return Decimal(wei_value) / Decimal(1e18)

def get_chain_name(chain_id, chain_id_to_metadata):
    return chain_id_to_metadata.get(int(chain_id), {}).get("name", f"Chain {chain_id}")

def load_operator_address(operate_home):
    ethereum_json_path = operate_home / "wallets" / "ethereum.json"
    try:
        with open(ethereum_json_path, "r") as f:
            ethereum_data = json.load(f)
        operator_address = ethereum_data.get("safes", {}).get("4")
        if not operator_address:
            print("Error: Operator address not found for chain ID 4 in the wallet file.")
            return None
        return operator_address
    except FileNotFoundError:
        print(f"Error: Ethereum wallet file not found at {ethereum_json_path}")
        return None
    except json.JSONDecodeError:
        print("Error: Ethereum wallet file contains invalid JSON.")
        return None

def validate_config(config):
    required_keys = ['home_chain_id', 'chain_configs']
    for key in required_keys:
        if key not in config:
            print(f"Error: '{key}' is missing in the configuration.")
            return False
    return True

def _get_agent_status() -> str:
    try:
        client = docker.from_env()
        container = client.containers.get("optimus_abci_0")
        is_running = container.status == "running"
        return _color_bool(is_running, "Running", "Stopped")
    except docker.errors.NotFound:
        return _color_string("Not Found", ColorCode.RED)
    except docker.errors.DockerException as e:
        print(f"Error: Docker exception occurred - {str(e)}")
        return _color_string("Error", ColorCode.RED)

def print_box(text: str, margin: int = 1, character: str = "=") -> None:
    """Print text centered within a box."""

    lines = text.split("\n")
    text_length = max(len(line) for line in lines)
    length = text_length + 2 * margin

    border = character * length
    margin_str = " " * margin

    print(border)
    print(f"{margin_str}{text}{margin_str}")
    print(border)
    print()


def print_title(text: str) -> None:
    """Print title."""
    print()
    print_box(text, 4, "=")


def print_section(text: str) -> None:
    """Print section."""
    print_box(text, 1, "-")


def wei_to_unit(wei: int) -> float:
    """Convert Wei to unit."""
    return wei / 1e18


def wei_to_token(wei: int, token: str = "xDAI") -> str:
    """Convert Wei to token."""
    return f"{wei_to_unit(wei):.6f} {token}"


def ask_confirm_password() -> str:
    password = getpass.getpass("Please enter a password: ")
    confirm_password = getpass.getpass("Please confirm your password: ")

    if password == confirm_password:
        return password
    else:
        print("Passwords do not match. Terminating.")
        sys.exit(1)


def check_rpc(rpc_url: str) -> None:
    spinner = Halo(text=f"Checking RPC...", spinner="dots")
    spinner.start()

    rpc_data = {
        "jsonrpc": "2.0",
        "method": "eth_newFilter",
        "params": ["invalid"],
        "id": 1,
    }

    try:
        response = requests.post(
            rpc_url, json=rpc_data, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        rpc_response = response.json()
    except Exception as e:
        print("Error: Failed to send RPC request:", e)
        sys.exit(1)

    rpc_error_message = rpc_response.get("error", {}).get(
        "message", "Exception processing RPC response"
    )

    if rpc_error_message == "Exception processing RPC response":
        print(
            "Error: The received RPC response is malformed. Please verify the RPC address and/or RPC behavior."
        )
        print("  Received response:")
        print("  ", rpc_response)
        print("")
        print("Terminating script.")
        sys.exit(1)
    elif rpc_error_message == "Out of requests":
        print("Error: The provided RPC is out of requests.")
        print("Terminating script.")
        sys.exit(1)
    elif (
        rpc_error_message == "The method eth_newFilter does not exist/is not available"
    ):
        print("Error: The provided RPC does not support 'eth_newFilter'.")
        print("Terminating script.")
        sys.exit(1)
    elif rpc_error_message == "invalid params":
        spinner.succeed("RPC checks passed.")
    else:
        print("Error: Unknown RPC error.")
        print("  Received response:")
        print("  ", rpc_response)
        print("")
        print("Terminating script.")
        sys.exit(1)


def input_with_default_value(prompt: str, default_value: str) -> str:
    user_input = input(f"{prompt} [{default_value}]: ")
    return str(user_input) if user_input else default_value


def input_select_chain(options: t.List[ChainType]):
    """Chose a single option from the offered ones"""
    user_input = input_with_default_value(
        f"Chose one of the following options {[option.name for option in options]}", "GNOSIS"
    )
    try:
        return ChainType.from_string(user_input.upper())
    except ValueError:
        print("Invalid option selected. Please try again.")
        return input_select_chain(options)


def load_api_keys(local_config: MechQuickstartConfig) -> t.Dict[str, t.List[str]]:
    """Load API keys from a file."""
    try:
        path = OPERATE_HOME / local_config.api_keys_path
        with open(path, "r") as f:
            api_keys = json.load(f)
    except FileNotFoundError:
        print(f"Error: API keys file not found at {local_config.api_keys_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: API keys file contains invalid JSON.")
        sys.exit(1)
    return api_keys


def get_local_config() -> MechQuickstartConfig:
    """Get local mech_quickstart configuration."""
    path = OPERATE_HOME / "local_config.json"
    if path.exists():
        mech_quickstart_config = MechQuickstartConfig.load(path)
    else:
        mech_quickstart_config = MechQuickstartConfig(path)

    print_section("API Key Configuration")

    if mech_quickstart_config.home_chain_id is None:
        print("Select the chain for you service")
        mech_quickstart_config.home_chain_id = input_select_chain([ChainType.GNOSIS]).id

    if mech_quickstart_config.gnosis_rpc is None:
        mech_quickstart_config.gnosis_rpc = input(
            f"Please enter a {ChainType.from_id(mech_quickstart_config.home_chain_id).name} RPC URL: "
        )
    
    if mech_quickstart_config.mech_hash is None:
        mech_hash = (
                input(
                    f"Do you want to set the mech_hash dict(set to {DEFAULT_MECH_HASH})? (y/n): "
                ).lower()
                == "y"
        )
        if mech_hash:
            while True:
                user_input = input(f"Please enter the mech_hash: ")
                mech_quickstart_config.mech_hash = user_input
                break
        else:
            mech_quickstart_config.mech_hash = DEFAULT_MECH_HASH

    if mech_quickstart_config.password_migrated is None:
        mech_quickstart_config.password_migrated = False

    if mech_quickstart_config.api_keys_path is None:
        mech_quickstart_config.api_keys_path = input_with_default_value("Please provide the path to your api_keys.json file", "../.api_keys.json")

    # test that api key path exists and is valid json
    load_api_keys(mech_quickstart_config)

    if mech_quickstart_config.metadata_hash is None:
        # TODO: default value is not a good idea here, we need to think of better ways to do this.
        mech_quickstart_config.metadata_hash = input_with_default_value("Please provide the metadata hash", "f01701220caa53607238e340da63b296acab232c18a48e954f0af6ff2b835b2d93f1962f0")

    if mech_quickstart_config.tools_to_packages_hash is None:
        tools_to_packages_hash = (
            input(
                f"Do you want to set the tools_to_packages_hash dict(set to {DEFAULT_TOOLS_TO_PACKAGE_HASH})? (y/n): "
            ).lower()
            == "y"
        )
        if tools_to_packages_hash:
            while True:
                user_input = input(f"Please enter the tools_to_packages_hash dict: ")
                tools_to_packages_hash = ast.literal_eval(user_input)
                if not isinstance(tools_to_packages_hash, dict):
                    print("Error: Please enter a valid dict.")
                    continue
                else:
                    mech_quickstart_config.tools_to_packages_hash = (
                        tools_to_packages_hash
                    )
                    break
        else:
            mech_quickstart_config.tools_to_packages_hash = (
                DEFAULT_TOOLS_TO_PACKAGE_HASH
            )

    mech_quickstart_config.store()
    return mech_quickstart_config


def apply_env_vars(env_vars: t.Dict[str, str]) -> None:
    """Apply environment variables."""
    for key, value in env_vars.items():
        if value is not None:
            os.environ[key] = str(value)


def handle_password_migration(
    operate: OperateApp, config: MechQuickstartConfig
) -> t.Optional[str]:
    """Handle password migration."""
    if not config.password_migrated:
        print("Add password...")
        old_password, new_password = "12345", ask_confirm_password()
        operate.user_account.update(old_password, new_password)
        if operate.wallet_manager.exists(LedgerType.ETHEREUM):
            operate.password = old_password
            wallet = operate.wallet_manager.load(LedgerType.ETHEREUM)
            wallet.crypto.dump(str(wallet.key_path), password=new_password)
            wallet.password = new_password
            wallet.store()

        config.password_migrated = True
        config.store()
        return new_password
    return None


def get_erc20_balance(ledger_api: LedgerApi, token: str, account: str) -> int:
    """Get ERC-20 token balance of an account."""
    web3 = t.cast(EthereumApi, ledger_api).api

    # ERC20 Token Standard Partial ABI
    erc20_abi = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }
    ]

    # Create contract instance
    contract = web3.eth.contract(address=web3.to_checksum_address(token), abi=erc20_abi)

    # Get the balance of the account
    balance = contract.functions.balanceOf(web3.to_checksum_address(account)).call()

    return balance



def get_service(manager: ServiceManager, template: ServiceTemplate) -> Service:
    if len(manager.json) > 0:
        old_hash = manager.json[0]["hash"]
        if old_hash == template["hash"]:
            print(f'Loading service {template["hash"]}')
            service = manager.load_or_create(
                hash=template["hash"],
                service_template=template,
            )
        else:
            print(f"Updating service from {old_hash} to " + template["hash"])
            service = manager.update_service(
                old_hash=old_hash,
                new_hash=template["hash"],
                service_template=template,
            )
    else:
        print(f'Creating service {template["hash"]}')
        service = manager.load_or_create(
            hash=template["hash"],
            service_template=template,
        )

    return service


def unit_to_wei(unit: float) -> int:
    """Convert unit to Wei."""
    return int(unit * 1e18)


CHAIN_TO_MARKETPLACE = {
     ChainType.GNOSIS: "0x4554fE75c1f5576c1d7F765B2A036c199Adae329",
}

CHAIN_TO_AGENT_FACTORY = {
    ChainType.GNOSIS: "0x6D8CbEbCAD7397c63347D44448147Db05E7d17B0",
}

def fetch_token_price(url: str, headers: dict) -> t.Optional[float]:
    """Fetch the price of a token from a given URL."""
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(
                f"Error fetching info from url {url}. Failed with status code: {response.status_code}"
            )
            return None
        prices = response.json()
        token = next(iter(prices))
        return prices[token].get("usd", None)
    except Exception as e:
        print(f"Error fetching token price: {e}")
        return None

def deploy_mech(sftxb: EthSafeTxBuilder, local_config: MechQuickstartConfig, service: Service) -> None:
    """Deploy the Mech service."""
    print_section("Creating a new Mech On Chain")
    chain_type = ChainType.from_id(int(local_config.home_chain_id))
    path = OPERATE_HOME / Path("../contracts/MechAgentFactory.json")
    abi = json.loads(path.read_text())["abi"]
    instance = web3.Web3()

    mech_marketplace_address = CHAIN_TO_MARKETPLACE[chain_type]
    # 0.01xDAI hardcoded for price
    # better to be configurable and part of local config
    mech_request_price = unit_to_wei(0.01)
    contract = instance.eth.contract(address=Web3.to_checksum_address(mech_marketplace_address), abi=abi)
    data = contract.encodeABI("create", args=[
        service.chain_configs[service.home_chain_id].chain_data.multisig,
        bytes.fromhex(local_config.metadata_hash.lstrip("f01701220")),
        mech_request_price,
        mech_marketplace_address
    ])
    tx_dict = {
        "to": CHAIN_TO_AGENT_FACTORY[chain_type],
        "data": data,
        "value": 0,
        "operation": SafeOperation.CALL,
    }
    receipt = sftxb.new_tx().add(tx_dict).settle()
    event = contract.events.CreateMech().process_receipt(receipt)[0]
    mech_address, agent_id = event["args"]["mech"], event["args"]["agentId"]
    print(f"Mech address: {mech_address}")
    print(f"Agent ID: {agent_id}")

    local_config.mech_address = mech_address
    local_config.agent_id = agent_id
    local_config.store()

def generate_mech_config(local_config: MechQuickstartConfig) -> dict:
    """Generate the Mech configuration."""
    mech_to_config = {
        local_config.mech_address: {
            "use_dynamic_pricing": False,
            "is_marketplace_mech": True,
        }
    }
    return mech_to_config

