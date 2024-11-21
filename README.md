<h1 align="center">
<b>Mech Quickstart</b>
</h1>

The Mech agent currently operates on the following chains:

-   Gnosis

See [here](https://github.com/valory-xyz/mech?tab=readme-ov-file#user-flow) for what it does.

## Terms and Conditions Disclaimer

> :warning: **Warning** <br />
> The code within this repository is provided without any warranties. It leverages third party APIs and it is important to note that the code has not been audited for potential security vulnerabilities.
> Using this code could potentially lead to loss of funds, compromised data, or asset risk.
> Exercise caution and use this code at your own risk. Please refer to the [LICENSE](./LICENSE) file for details about the terms and conditions.

## Compatible Systems

-   Windows 10/11: WSL2
-   Mac ARM / Intel
-   Linux
-   Raspberry Pi 4

## System Requirements

Ensure your machine satisfies the requirements:

-   Python `==3.10`
-   [Poetry](https://python-poetry.org/docs/) `>=1.4.0`
-   [Docker Engine](https://docs.docker.com/engine/install/)
-   [Docker Compose](https://docs.docker.com/compose/install/)

## Setup Requirements

-   For the initial setup you will need to fund certain addresses with the following funds when requested: 0.05 xDAI. These quantities are based on the gas prices seen on the 1st half of Sept 2024 and may need to be revised. Additionally some quantity of OLAS for staking.

-   You need 1 RPC for your agent instance for Gnosis.

## Setting up Mech metadata hash file

1.  Copy over the sample from .metadata_hash.json.example. The example file is valid for a single tool.

    ```
    cp .metadata_hash.json.example .metadata_hash.json
    ```

2.  Define your top level key value pairs
    | Name | Value Type | Description |
    | :--- | :---: | :--- |
    | Name | str | Name of your mech |
    | Description | str | Description of your mech |
    | inputFormat | str | Can leave it default |
    | outputFormat | str | Can leave it default |
    | image | str | Link to the imagerepresenting your mech |
    | tools | List | List of AI tools your mech supports |
    | toolMetadata | Dict | Provides more info on sprecific tools |

> [!IMPORTANT] \
> Each tool mentioned in `tools` should have a corresponding `key` in the `toolsMetadata`.

3.  Define your key value pairs for each specific tools.

    | Name         | Value Type | Description                             |
    | :----------- | :--------: | :-------------------------------------- |
    | Name         |    str     | Name of the AI tool                     |
    | Description  |    str     | Description of the AI tool              |
    | input        |    Dict    | Contains the input schema of the tool   |
    | output       |    Dict    | Contains the output schema of the tool  |
    | image        |    str     | Link to the imagerepresenting your mech |
    | tools        |    List    | List of AI tools your mech supports     |
    | toolMetadata |    Dict    | Provides more info on sprecific tools   |

> [!IMPORTANT] \
> Each field mentioned in `required` should have a corresponding `key` in the `properties`.

4.  Define your key value pairs for the output schema

    | Name       | Value Type | Description                                                  |
    | :--------- | :--------: | :----------------------------------------------------------- |
    | type       |    str     | Mentions the type of the schema                              |
    | properties |    Dict    | Contains the required output data                            |
    | required   |    List    | Contains the list of fields required in the `properties` key |

5.  Define your key value pairs for the properties field

    | Name      | Value Type | Description                                                   |
    | :-------- | :--------: | :------------------------------------------------------------ |
    | requestId |    Dict    | Contains the request id and it's description                  |
    | result    |    Dict    | Contains the result and it's description with an example      |
    | prompt    |    Dict    | Contains the prompt used for the request and it's description |

## Setting up api keys file

1. Copy over the sample from .api_keys.json.example.

    ```
    cp .api_keys.json.example .api_keys.json
    ```

2. Setup key value pairs for every AI tool your mech uses

    - The name of the tool will be the `key` used in the file
    - The value will be an array of valid API keys the tool can use

## Run the Service

1.  Clone this repository:

    ```
    git clone git@github.com:valory-xyz/mech-quickstart.git
    ```

2.  Create the virtual environment:
    ```
    cd mech-quickstart
    poetry shell
    poetry install
    ```
3.  Run the quickstart:

        ```bash
        python run_service.py
        ```

    When prompted, add the requested info, send funds to the prompted address and you're good to go!

### Creating a local user account

When run for the first time, the agent will setup for you a password protected local account. You will be asked to enter and confirm a password as below.
Please be mindful of storing it in a secure space, for future use. **Hint:** If you do not want to use a password just press Enter when asked to enter and confirm your password.

```bash
Creating a new local user account...
Please enter a password:
Please confirm your password:
Creating the main wallet...
```

### Notes:

-   Staking is currently in a testing phase, so the number of trader agents that can be staked might be limited.
-   Within each staking period (24hrs) staking happens after the agent has reached its staking contract's KPIs. In the current agent's version, this takes approxiamtely 45 minutes of activity.
-   In case a service becomes inactive and remains so for more than 2 staking periods (approx. 48 hours), it faces eviction from the staking program and ceases to accrue additional rewards.

### Service is Running

Once the command has completed, i.e. the service is running, you can see the live logs with:

```bash
docker logs mech_abci_0 --follow
```

To stop your agent, use:

```bash
./stop_service.sh
```

## Update between versions

Simply pull the latest script:

```bash
git pull origin
```

Then continue above with "Run the script".

## What's New

...

## Advice for Windows users on installing Windows Subsystem for Linux version 2 (WSL2)

1. Open a **Command Prompt** terminal as an Administrator.

2. Run the following commands:

    ```bash
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    ```

    ```bash
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    ```

3. Then restart the computer.

4. Open a **Command Prompt** terminal.

5. Make WSL2 the default version by running:

    ```bash
    wsl --set-default-version 2
    ```

6. Install Ubuntu 22.04 by running:

    ```bash
    wsl --install -d Ubuntu-22.04
    ```

7. Follow the on-screen instructions and set a username and password for your Ubuntu installation.

8. Install Docker Desktop and enable the WSL 2 backend by following the instructions from Docker [here](https://docs.docker.com/desktop/wsl/).

## Known issues
