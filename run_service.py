# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------
"""Mech Quickstart script."""

import getpass
import json
import os
import sys
import time
import typing as t

from dotenv import load_dotenv
from halo import Halo

from operate.account.user import UserAccount
from operate.cli import OperateApp
from operate.ledger.profiles import CONTRACTS, STAKING, OLAS
from operate.types import (
    LedgerType,
    ServiceTemplate,
    ConfigurationTemplate,
    FundRequirementsTemplate,
    ChainType,
    OnChainState,
)
from utils import print_title, print_section, get_local_config, get_service, ask_confirm_password, \
    handle_password_migration, print_box, wei_to_token, get_erc20_balance, CHAIN_TO_MARKETPLACE, apply_env_vars, \
    unit_to_wei, MechQuickstartConfig, OPERATE_HOME, load_api_keys, deploy_mech, generate_mech_config

load_dotenv()

WALLET_TOPUP = unit_to_wei(0.5)
MASTER_SAFE_TOPUP = unit_to_wei(0)
SAFE_TOPUP = unit_to_wei(0)
AGENT_TOPUP = unit_to_wei(1.5)

COST_OF_BOND = 1
COST_OF_STAKING = 10**20  # 100 OLAS
COST_OF_BOND_STAKING = 5 * 10**19  # 50 OLAS


CHAIN_ID_TO_METADATA = {
    100: {
        "name": "Gnosis",
        "token": "xDAI",
        "firstTimeTopUp": unit_to_wei(2),
        "operationalFundReq": MASTER_SAFE_TOPUP,
        "usdcRequired": False,
        "gasParams": {
            # this means default values will be used
            "MAX_PRIORITY_FEE_PER_GAS": "",
            "MAX_FEE_PER_GAS": "",
        },
    },
}

# @note patching operate -> legder -> profiles.py -> staking dict for gnosis
STAKING[ChainType.GNOSIS]["mech_marketplace"] = "0x998dEFafD094817EF329f6dc79c703f1CF18bC90"
FALLBACK_STAKING_PARAMS = {
    ChainType.GNOSIS: dict(
        agent_ids=[37],
        service_registry=CONTRACTS[ChainType.GNOSIS]["service_registry"],  # nosec
        staking_token=STAKING[ChainType.GNOSIS]["mech_marketplace"],  # nosec
        service_registry_token_utility=CONTRACTS[ChainType.GNOSIS][
            "service_registry_token_utility"
        ],  # nosec
        min_staking_deposit=COST_OF_STAKING,
        activity_checker="0x32B5A40B43C4eDb123c9cFa6ea97432380a38dDF",  # nosec
    ),
}

def get_service_template(config: MechQuickstartConfig) -> ServiceTemplate:
    """Get the service template"""
    return ServiceTemplate(
        {
            "name": "mech_quickstart",
            "hash": str(config.mech_hash),
            "description": "The mech executes AI tasks requested on-chain and delivers the results to the requester.",
            "image": "https://gateway.autonolas.tech/ipfs/bafybeidzpenez565d7vp7jexfrwisa2wijzx6vwcffli57buznyyqkrceq",
            "service_version": "v0.1.0",
            "home_chain_id": str(config.home_chain_id),
            "configurations": {
                str(config.home_chain_id): ConfigurationTemplate(
                    {
                        "staking_program_id": "mech_marketplace",
                        "rpc": config.gnosis_rpc,
                        "nft": "bafybeifgj3kackzfoq4fxjiuousm6epgwx7jbc3n2gjwzjgvtbbz7fc3su",
                        "cost_of_bond": COST_OF_BOND,
                        "threshold": 1,
                        "use_staking": True,
                        "fund_requirements": FundRequirementsTemplate(
                            {
                                "agent": AGENT_TOPUP,
                                "safe": SAFE_TOPUP,
                            }
                        ),
                    }
                ),
            },
        }
    )

def main() -> None:
    """Run service."""

    print_title("Mech Quickstart")
    print("This script will assist you in setting up and running the mech service.")
    print()

    print_section("Set up local user account")
    operate = OperateApp(
        home=OPERATE_HOME,
    )
    operate.setup()

    mech_quickstart_config = get_local_config()
    template = get_service_template(mech_quickstart_config)
    manager = operate.service_manager()
    service = get_service(manager, template)

    # Create a new account
    if operate.user_account is None:
        print("Creating a new local user account...")
        password = ask_confirm_password()
        UserAccount.new(
            password=password,
            path=operate._path / "user.json",
        )
        mech_quickstart_config.password_migrated = True
        mech_quickstart_config.store()
    else:
        password = getpass.getpass("Enter local user account password: ")

    operate.password = password

    # Create the main wallet
    if not operate.wallet_manager.exists(ledger_type=LedgerType.ETHEREUM):
        print("Creating the main wallet...")
        wallet, mnemonic = operate.wallet_manager.create(
            ledger_type=LedgerType.ETHEREUM
        )
        wallet.password = password
        print()
        print_box(
            f"Please save the mnemonic phrase for the main wallet:\n{', '.join(mnemonic)}",
            0,
            "-",
        )
        input("Press enter to continue...")

    # Load the main wallet
    else:
        wallet = operate.wallet_manager.load(ledger_type=LedgerType.ETHEREUM)

    manager = operate.service_manager()

    # Iterate the chain configs
    for chain_id, configuration in service.chain_configs.items():
        chain_metadata = CHAIN_ID_TO_METADATA[int(chain_id)]
        chain_config = service.chain_configs[chain_id]
        chain_type = chain_config.ledger_config.chain
        ledger_api = wallet.ledger_api(
            chain_type=chain_type,
            rpc=chain_config.ledger_config.rpc,
        )
        os.environ["CUSTOM_CHAIN_RPC"] = chain_config.ledger_config.rpc
        os.environ["OPEN_AUTONOMY_SUBGRAPH_URL"] = (
            "https://subgraph.autonolas.tech/subgraphs/name/autonolas-staging"
        )
        service_exists = (
            manager._get_on_chain_state(chain_config) != OnChainState.NON_EXISTENT
        )

        chain_name, token = chain_metadata["name"], chain_metadata["token"]
        balance_str = wei_to_token(ledger_api.get_balance(wallet.crypto.address), token)
        print(
            f"[{chain_name}] Main wallet balance: {balance_str}",
        )
        safe_exists = wallet.safes.get(chain_type) is not None
        required_balance = (
            chain_metadata["firstTimeTopUp"]
            if not safe_exists
            else chain_metadata["operationalFundReq"]
        )
        print(
            f"[{chain_name}] Please make sure main wallet {wallet.crypto.address} has at least {wei_to_token(required_balance, token)}",
        )
        spinner = Halo(text=f"[{chain_name}] Waiting for funds...", spinner="dots")
        spinner.start()

        while ledger_api.get_balance(wallet.crypto.address) < required_balance:
            time.sleep(1)

        spinner.succeed(
            f"[{chain_name}] Main wallet updated balance: {wei_to_token(ledger_api.get_balance(wallet.crypto.address), token)}."
        )
        print()

        # Create the master safe
        if not safe_exists:
            print(f"[{chain_name}] Creating Safe")
            ledger_type = LedgerType.ETHEREUM
            wallet_manager = operate.wallet_manager
            wallet = wallet_manager.load(ledger_type=ledger_type)

            wallet.create_safe(  # pylint: disable=no-member
                chain_type=chain_type,
                rpc=chain_config.ledger_config.rpc,
            )

        print_section(f"[{chain_name}] Set up the service in the Olas Protocol")

        address = wallet.safes[chain_type]
        if not service_exists:
            first_time_top_up = chain_metadata["firstTimeTopUp"]
            print(
                f"[{chain_name}] Please make sure master safe address {address} has at least {wei_to_token(first_time_top_up, token)}."
            )
            spinner = Halo(
                text=f"[{chain_name}] Waiting for funds...",
                spinner="dots",
            )
            spinner.start()

            while ledger_api.get_balance(address) < first_time_top_up:
                print(f"[{chain_name}] Funding Safe")
                wallet.transfer(
                    to=t.cast(str, wallet.safes[chain_type]),
                    amount=int(chain_metadata["firstTimeTopUp"]),
                    chain_type=chain_type,
                    from_safe=False,
                    rpc=chain_config.ledger_config.rpc,
                )
                time.sleep(1)

            spinner.succeed(
                f"[{chain_name}] Safe updated balance: {wei_to_token(ledger_api.get_balance(address), token)}."
            )

        if chain_config.chain_data.user_params.use_staking and not service_exists:
            olas_address = OLAS[chain_type]
            print(
                f"[{chain_name}] Please make sure address {address} has at least {wei_to_token(COST_OF_STAKING + COST_OF_BOND_STAKING, olas_address)}"
            )

            spinner = Halo(
                text=f"[{chain_name}] Waiting for {olas_address}...",
                spinner="dots",
            )
            spinner.start()

            while (
                get_erc20_balance(ledger_api, olas_address, address)
                < COST_OF_STAKING + COST_OF_BOND_STAKING
            ):
                time.sleep(1)

            balance = get_erc20_balance(ledger_api, olas_address, address) / 10**18
            spinner.succeed(
                f"[{chain_name}] Safe updated balance: {balance} {olas_address}"
            )

        manager.deploy_service_onchain_from_safe_single_chain(
            hash=service.hash,
            chain_id=chain_id,
            fallback_staking_params=FALLBACK_STAKING_PARAMS[chain_type],
        )

        # Fund the service
        manager.fund_service(
            hash=service.hash,
            chain_id=chain_id,
            safe_fund_treshold=SAFE_TOPUP,
            safe_topup=SAFE_TOPUP,
        )
    home_chain_id = service.home_chain_id
    home_chain_type = ChainType.from_id(int(home_chain_id))


    # deploy a mech if doesnt exist already
    if not mech_quickstart_config.agent_id:
        chain_config = service.chain_configs[home_chain_id]
        ledger_config = chain_config.ledger_config
        sftxb = manager.get_eth_safe_tx_builder(ledger_config)
        # reload the service to get the latest version of it
        service = get_service(manager, template)
        deploy_mech(sftxb, mech_quickstart_config, service)

    # Apply env cars
    api_keys = load_api_keys(mech_quickstart_config)
    mech_to_config = generate_mech_config(mech_quickstart_config)
    env_vars = {
        "SERVICE_REGISTRY_ADDRESS": CONTRACTS[home_chain_type]["service_registry"],
        "STAKING_TOKEN_CONTRACT_ADDRESS": STAKING[home_chain_type]["mech_marketplace"],
        "MECH_MARKETPLACE_ADDRESS": CHAIN_TO_MARKETPLACE[home_chain_type],
        # TODO: no way to update this atm after its provided, user is expected to update the file itself.
        "API_KEYS": json.dumps(api_keys, separators=(',', ':')),
        "AGENT_ID": str(mech_quickstart_config.agent_id),
        # TODO this will be very unclear for the general user how to come up with
        "METADATA_HASH": mech_quickstart_config.metadata_hash,
        "MECH_TO_CONFIG": json.dumps(mech_to_config, separators=(',', ':')),
        "ON_CHAIN_SERVICE_ID": service.chain_configs[home_chain_id].chain_data.token,
        "TOOLS_TO_PACKAGE_HASH": mech_quickstart_config.tools_to_packages_hash,
    }
    apply_env_vars(env_vars)

    # Build the deployment
    # del os.environ["MAX_FEE_PER_GAS"]
    # del os.environ["MAX_PRIORITY_FEE_PER_GAS"]
    service.deployment.build(use_docker=True, force=True, chain_id=home_chain_id)

    # Run the deployment
    service.deployment.start(use_docker=True)
    print()
    print_section("Running the service")


if __name__ == "__main__":
    main()
