import json

from brownie import accounts
from brownie.network.gas.strategies import GasNowScalingStrategy
from brownie.project import load as load_project
from brownie.project.main import get_loaded_projects

# set a throwaway admin account here
DEPLOYER = accounts.add(private_key = 'YOUR_PRIVATE_KEY')
REQUIRED_CONFIRMATIONS = 1

# deployment settings
# most settings are taken from `contracts/pools/{POOL_NAME}/pooldata.json`
POOL_NAME = "3pool"

# temporary owner address
POOL_OWNER = "0x3C8b2B2C71AcdA9Ed2aCf44273C159b1aC8381d9"
GAUGE_OWNER = "0x3C8b2B2C71AcdA9Ed2aCf44273C159b1aC8381d9"

MINTER = "0x3C8b2B2C71AcdA9Ed2aCf44273C159b1aC8381d9"

# POOL_OWNER = "0xeCb456EA5365865EbAb8a2661B0c503410e9B347"  # PoolProxy
# GAUGE_OWNER = "0x519AFB566c05E00cfB9af73496D00217A630e4D5"  # GaugeProxy


def _tx_params():
    return {
        "from": DEPLOYER,
        "required_confs": REQUIRED_CONFIRMATIONS,
        "gas_price": 5000000000,
    }


def main():
    project = get_loaded_projects()[0]
    balance = DEPLOYER.balance()

    # load data about the deployment from `pooldata.json`
    contracts_path = project._path.joinpath("contracts/pools")
    with contracts_path.joinpath(f"{POOL_NAME}/pooldata.json").open() as fp:
        pool_data = json.load(fp)

    swap_name = next(i.stem for i in contracts_path.glob(f"{POOL_NAME}/StableSwap*"))
    swap_deployer = getattr(project, swap_name)
    token_deployer = getattr(project, pool_data.get("lp_contract"))

    underlying_coins = [i["underlying_address"] for i in pool_data["coins"]]
    wrapped_coins = [i.get("wrapped_address", i["underlying_address"]) for i in pool_data["coins"]]

    base_pool = None
    if "base_pool" in pool_data:
        with contracts_path.joinpath(f"{pool_data['base_pool']}/pooldata.json").open() as fp:
            base_pool_data = json.load(fp)
            base_pool = base_pool_data["swap_address"]

    # deploy the token
    token_args = pool_data["lp_constructor"]
    token = token_deployer.deploy(token_args["name"], token_args["symbol"], _tx_params())
    print(f"lp_token_address: {token.address}")

    # deploy the pool
    abi = next(i["inputs"] for i in swap_deployer.abi if i["type"] == "constructor")
    args = pool_data["swap_constructor"]
    args.update(
        _coins=wrapped_coins,
        _underlying_coins=underlying_coins,
        _pool_token=token,
        _base_pool=base_pool,
        _owner=POOL_OWNER,
    )
    deployment_args = [args[i["name"]] for i in abi] + [_tx_params()]

    swap = swap_deployer.deploy(*deployment_args)
    print(f"swap_address: {swap.address}")

    # set the minter
    token.set_minter(swap, _tx_params())

    print(f"Gas used in deployment: {(balance - DEPLOYER.balance()) / 1e18:.4f} ETH")
