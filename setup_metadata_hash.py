import sys
import json
from typing import Tuple, List, Dict
import multibase
import multicodec
from aea.helpers.cid import to_v1
from aea_cli_ipfs.ipfs_utils import IPFSTool
from utils import (
    print_title,
    MechQuickstartConfig,
    input_with_default_value,
)


metadata_schema = {
    "name": str,
    "description": str,
    "inputFormat": str,
    "outputFormat": str,
    "image": str,
    "tools": List,
    "toolMetadata": Dict,
}

tool_schema = {
    "name": str,
    "description": str,
    "input": Dict,
    "output": Dict,
}
tool_input_schema = {
    "type": str,
    "description": str,
}
tool_output_schema = {"type": str, "description": str, "schema": Dict}

output_schema_schema = {
    "properties": Dict,
    "required": List,
    "type": str,
}

properties_schema = {
    "requestId": Dict,
    "result": Dict,
    "prompt": Dict,
}

properties_data_schema = {
    "type": str,
    "description": str,
}


def setup_metadata_hash(mech_quickstart_config: MechQuickstartConfig) -> None:
    """
    Push the metadata file to IPFS.
    """

    print_title("Mech Quickstart: Metadata hash setup")

    metadata_hash_path = input_with_default_value(
        "Please provide the path to your metadata_hash.json file",
        "./.metadata_hash.json",
    )

    status, error_msg = __validate_metadata_file(metadata_hash_path)
    if not status:
        print(error_msg)
        print("Please refer to .metadata_hash.json.example for reference")
        sys.exit(1)

    response = IPFSTool().client.add(
        metadata_hash_path, pin=True, recursive=True, wrap_with_directory=False
    )
    v1_file_hash = to_v1(response["Hash"])
    cid_bytes = multibase.decode(v1_file_hash)
    multihash_bytes = multicodec.remove_prefix(cid_bytes)
    v1_file_hash_hex = "f01" + multihash_bytes.hex()

    mech_quickstart_config.metadata_hash = v1_file_hash_hex

    print_title("Metadata hash successfully generated and stored in config")


def __validate_metadata_file(file_path) -> Tuple[bool, str]:
    status = False
    try:
        path = file_path
        with open(path, "r") as f:
            metadata: Dict = json.load(f)

    except FileNotFoundError:
        return (status, f"Error: Metadata file not found at {file_path}")
    except json.JSONDecodeError:
        return (status, "Error: Metadata file contains invalid JSON.")

    for key, expected_type in metadata_schema.items():
        if key not in metadata:
            return (status, f"Missing key in metadata json: '{key}'")

        if not isinstance(metadata[key], expected_type):
            expected = expected_type.__name__
            actual = type(metadata[key]).__name__
            return (
                status,
                f"Invalid type for key in metadata json. Expected '{expected}', but got '{actual}'",
            )

    tools = metadata["tools"]
    tools_metadata = metadata["toolMetadata"]
    num_of_tools = len(tools)
    num_of_tools_metadata = len(tools_metadata)

    if num_of_tools != num_of_tools_metadata:
        return (
            status,
            f"Number of tools does not match number of keys in 'toolMetadata'. Expected {num_of_tools} but got {num_of_tools_metadata}.",
        )

    for tool in tools:
        if tool not in tools_metadata:
            return (status, f"Missing toolsMetadata for tool: '{tool}'")

        for key, expected_type in tool_schema.items():
            data = tools_metadata[tool]
            if key not in data:
                return (status, f"Missing key in toolsMetadata: '{key}'")

            if not isinstance(data[key], expected_type):
                expected = expected_type.__name__
                actual = type(data[key]).__name__
                return (
                    status,
                    f"Invalid type for key in toolsMetadata. Expected '{expected}', but got '{actual}'",
                )

            if key == "input":
                for i_key, i_expected_type in tool_input_schema.items():
                    input_data = data[key]
                    if i_key not in input_data:
                        return (
                            status,
                            f"Missing key for {tool} -> input: '{i_key}'",
                        )

                    if not isinstance(input_data[i_key], i_expected_type):
                        i_expected = i_expected_type.__name__
                        i_actual = type(input_data[i_key]).__name__
                        return (
                            status,
                            f"Invalid type for '{i_key}' in {tool} -> input. Expected '{i_expected}', but got '{i_actual}'.",
                        )

            elif key == "output":
                for o_key, o_expected_type in tool_output_schema.items():
                    output_data = data[key]
                    if o_key not in output_data:
                        return (
                            status,
                            f"Missing key for {tool} -> output: '{o_key}'",
                        )

                    if not isinstance(output_data[o_key], o_expected_type):
                        o_expected = o_expected_type.__name__
                        o_actual = type(output_data[o_key]).__name__
                        return (
                            status,
                            f"Invalid type for '{o_key}' in {tool} -> output. Expected '{o_expected}', but got '{o_actual}'.",
                        )

                    if o_key == "schema":
                        for (
                            s_key,
                            s_expected_type,
                        ) in output_schema_schema.items():
                            output_schema_data = output_data[o_key]
                            if s_key not in output_schema_data:
                                return (
                                    status,
                                    f"Missing key for {tool} -> output -> schema: '{s_key}'",
                                )

                            if not isinstance(
                                output_schema_data[s_key], s_expected_type
                            ):
                                s_expected = s_expected_type.__name__
                                s_actual = type(output_schema_data[s_key]).__name__
                                return (
                                    status,
                                    f"Invalid type for '{s_key}' in {tool} -> output -> schema. Expected '{s_expected}', but got '{s_actual}'.",
                                )

                            if (
                                s_key == "properties"
                                and "required" in output_schema_data
                            ):
                                for (
                                    p_key,
                                    p_expected_type,
                                ) in properties_schema.items():
                                    properties_data = output_schema_data[s_key]
                                    if p_key not in properties_data:
                                        return (
                                            status,
                                            f"Missing key for {tool} -> output -> schema -> properties: '{p_key}'",
                                        )

                                    if not isinstance(
                                        properties_data[p_key], p_expected_type
                                    ):
                                        p_expected = p_expected_type.__name__
                                        p_actual = type(properties_data[p_key]).__name__
                                        return (
                                            status,
                                            f"Invalid type for '{p_key}' in {tool} -> output -> schema -> properties. Expected '{p_expected}', but got '{p_actual}'.",
                                        )

                                    required = output_schema_data["required"]
                                    num_of_properties_data = len(properties_data)
                                    num_of_required = len(required)

                                    if num_of_properties_data != num_of_required:
                                        return (
                                            status,
                                            f"Number of properties data does not match number of keys in 'required'. Expected {num_of_required} but got {num_of_properties_data}.",
                                        )

                                    for (
                                        key,
                                        expected_type,
                                    ) in properties_data_schema.items():
                                        data = properties_data[p_key]
                                        if key not in data:
                                            return (
                                                status,
                                                f"Missing key in properties -> {p_key}: '{key}'",
                                            )

                                        if not isinstance(data[key], expected_type):
                                            expected = expected_type.__name__
                                            actual = type(data[key]).__name__
                                            return (
                                                status,
                                                f"Invalid type for key in properties. Expected '{expected}', but got '{actual}'",
                                            )

    return (True, "")
