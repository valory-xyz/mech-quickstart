from typing import Tuple

import multibase
import multicodec
from aea.helpers.cid import to_v1
from aea_cli_ipfs.ipfs_utils import IPFSTool
from utils import (
    print_title,
    OPERATE_HOME,
    MechQuickstartConfig,
    input_with_default_value,
    OperateApp,
)


def main() -> None:
    """
    Push the metadata file to IPFS.
    """

    print_title("Mech Quickstart: Metadata hash setup")
    print("This script will assist you in setting up the metadata hash for your mech.")
    print()

    operate = OperateApp(
        home=OPERATE_HOME,
    )
    operate.setup()

    path = OPERATE_HOME / "local_config.json"
    if path.exists():
        mech_quickstart_config = MechQuickstartConfig.load(path)
    else:
        mech_quickstart_config = MechQuickstartConfig(path)

    metadata_hash_path = input_with_default_value(
        "Please provide the path to your metadata_hash.json file",
        "./.metadata_hash.json",
    )

    response = IPFSTool().client.add(
        metadata_hash_path, pin=True, recursive=True, wrap_with_directory=False
    )
    v1_file_hash = to_v1(response["Hash"])
    cid_bytes = multibase.decode(v1_file_hash)
    multihash_bytes = multicodec.remove_prefix(cid_bytes)
    v1_file_hash_hex = "f01" + multihash_bytes.hex()

    mech_quickstart_config.metadata_hash = v1_file_hash_hex
    mech_quickstart_config.store()

    print()
    print_title("Metadata hash successfully generated and stored in config")


if __name__ == "__main__":
    main()
