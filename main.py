import json
import logging
import sys
import time
import traceback
from ether.client import Web3Client
from ether.abis import erc20

from slack import send_notify
from v3_lp import V3LP
from config import conf


def add_liquidity(lp_cli: V3LP, tick_range=500, utilization=0.3):
    """
    把token0 token1 分别添加单边流动性
    """
    tick_range = int(tick_range)
    token0 = lp_cli.cli.eth.contract(lp_cli.token0, abi=erc20)
    token1 = lp_cli.cli.eth.contract(lp_cli.token1, abi=erc20)
    # 添加30%
    token0_to_add = int(
        token0.functions["balanceOf"](lp_cli.cli.acc.address).call() * utilization
    )
    token1_to_add = int(
        token1.functions["balanceOf"](lp_cli.cli.acc.address).call() * utilization
    )

    current_tick = lp_cli.current_tick()
    data = []
    data.append(
        {
            "tick_lower": current_tick - tick_range,
            "tick_upper": current_tick - 10,
            "amount0": token0_to_add,
            "amount1": token1_to_add,
        }
    )
    data.append(
        {
            "tick_lower": current_tick + 10,
            "tick_upper": current_tick + tick_range,
            "amount0": token0_to_add,
            "amount1": token1_to_add,
        }
    )
    return lp_cli.add_liquidity(data)


def poll_pair(lp_cli: V3LP,conf):
    """
    获取token_id, 如果不存在， 则添加流动性
    """
    now = time.time()
    nft_balance = lp_cli.balanceOf()
    # 没有流动性， 添加一波
    if nft_balance == 0:
        lp_cli.cli.eth.wait_for_transaction_receipt(add_liquidity(lp_cli, conf['init_tick_range'], conf['add_ratio']))
    else:
        token_ids = lp_cli.get_token_ids()
        # 已经存在流动性， 检查是否超时(缩小区间)
        logging.info(f'流动性持续时间 {now - lp_cli.last_add_ts} secs')
        if now - lp_cli.last_add_ts > 3600 * 6:
            pos = lp_cli.position_info(token_ids[0])
            old_lower, old_upper = lp_cli.position_ticks(pos)
            old_range = old_upper - old_lower + 10
            lp_cli.cli.eth.wait_for_transaction_receipt(lp_cli.remove_liquidity(token_ids))
            lp_cli.cli.eth.wait_for_transaction_receipt(add_liquidity(lp_cli, old_range / 2))
        else:
            # 已经存在流动性， 检查tick是否走出区间了
            token0_low, token0_up = lp_cli.position_ticks(
                lp_cli.position_info(token_ids[0])
            )
            token1_low, token1_up = lp_cli.position_ticks(
                lp_cli.position_info(token_ids[1])
            )
            old_range = token0_up - token0_low + 10
            current_tick = lp_cli.current_tick()
            if current_tick > token1_up or current_tick < token0_low:
                lp_cli.cli.eth.wait_for_transaction_receipt(lp_cli.remove_liquidity(token_ids))
                lp_cli.cli.eth.wait_for_transaction_receipt(add_liquidity(lp_cli, old_range * 1.5))


def main():
    cli = Web3Client["arb"].with_account(conf["private_key"])
    lp_cli = V3LP(
        cli,
        conf['token0'],
        conf['token1'],
        0,
        0,
    )
    while True:
        poll_pair(lp_cli,conf)
        time.sleep(5)

if __name__ == '__main__':
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    while True:
        try:
            main()
        except Exception as e:
            logging.error(e)
            traceback.print_exc()
            send_notify(f"""ERROR: {e}
{traceback.format_exc()}
""")
            time.sleep(3)