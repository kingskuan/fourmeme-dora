"""BSC on-chain interactions — token creation, LP, swaps."""
import json, logging
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from config.settings import settings

logger = logging.getLogger("perphunter.onchain")
PANCAKE_ROUTER_V3 = "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

TOKEN_MANAGER_ABI = json.loads('[{"name":"createToken","type":"function","inputs":[{"name":"createArg","type":"bytes"},{"name":"signature","type":"bytes"}],"outputs":[]}]')
ERC20_ABI = json.loads('[{"name":"approve","type":"function","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},{"name":"balanceOf","type":"function","inputs":[{"name":"account","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},{"name":"decimals","type":"function","inputs":[],"outputs":[{"name":"","type":"uint8"}]}]')
ROUTER_ABI = json.loads('[{"name":"exactInputSingle","type":"function","inputs":[{"name":"params","type":"tuple","components":[{"name":"tokenIn","type":"address"},{"name":"tokenOut","type":"address"},{"name":"fee","type":"uint24"},{"name":"recipient","type":"address"},{"name":"amountIn","type":"uint256"},{"name":"amountOutMinimum","type":"uint256"},{"name":"sqrtPriceLimitX96","type":"uint160"}]}],"outputs":[{"name":"amountOut","type":"uint256"}]}]')

class BSCChain:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.bsc.rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.account = Account.from_key(settings.wallet.private_key)
        self.address = self.account.address
        self.token_manager = self.w3.eth.contract(address=Web3.to_checksum_address(settings.four_meme.token_manager_v2), abi=TOKEN_MANAGER_ABI)
        self.router = self.w3.eth.contract(address=Web3.to_checksum_address(PANCAKE_ROUTER_V3), abi=ROUTER_ABI)

    def get_bnb_balance(self):
        return float(self.w3.from_wei(self.w3.eth.get_balance(self.address), "ether"))

    async def buy_token(self, token_address, bnb_amount, slippage_pct=5.0):
        amount_in = self.w3.to_wei(bnb_amount, "ether")
        nonce = self.w3.eth.get_transaction_count(self.address)
        amount_out_min = int(amount_in * (1 - slippage_pct / 100))
        params = {"tokenIn": Web3.to_checksum_address(WBNB), "tokenOut": Web3.to_checksum_address(token_address), "fee": 2500, "recipient": self.address, "amountIn": amount_in, "amountOutMinimum": amount_out_min, "sqrtPriceLimitX96": 0}
        tx = self.router.functions.exactInputSingle(params).build_transaction({"from": self.address, "value": amount_in, "nonce": nonce, "gas": 300000, "gasPrice": self.w3.eth.gas_price, "chainId": settings.bsc.chain_id})
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info(f"Buy tx: {tx_hash.hex()}")
        return tx_hash.hex()

    async def sell_token(self, token_address, amount_pct=100.0):
        token = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        balance = token.functions.balanceOf(self.address).call()
        sell_amount = int(balance * (amount_pct / 100))
        if sell_amount == 0: raise ValueError("No tokens")
        nonce = self.w3.eth.get_transaction_count(self.address)
        approve_tx = token.functions.approve(Web3.to_checksum_address(PANCAKE_ROUTER_V3), sell_amount).build_transaction({"from": self.address, "nonce": nonce, "gas": 100000, "gasPrice": self.w3.eth.gas_price, "chainId": settings.bsc.chain_id})
        self.w3.eth.send_raw_transaction(self.account.sign_transaction(approve_tx).raw_transaction)
        sell_amount_out_min = int(sell_amount * (1 - 5.0 / 100))
        params = {"tokenIn": Web3.to_checksum_address(token_address), "tokenOut": Web3.to_checksum_address(WBNB), "fee": 2500, "recipient": self.address, "amountIn": sell_amount, "amountOutMinimum": sell_amount_out_min, "sqrtPriceLimitX96": 0}
        tx = self.router.functions.exactInputSingle(params).build_transaction({"from": self.address, "nonce": nonce+1, "gas": 300000, "gasPrice": self.w3.eth.gas_price, "chainId": settings.bsc.chain_id})
        tx_hash = self.w3.eth.send_raw_transaction(self.account.sign_transaction(tx).raw_transaction)
        logger.info(f"Sell tx: {tx_hash.hex()}")
        return tx_hash.hex()
