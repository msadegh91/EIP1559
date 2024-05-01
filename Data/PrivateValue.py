from web3 import Web3 , HTTPProvider
#import web3_api
import requests
import sys
import numpy as np
from hexbytes import HexBytes
import csv
import bisect
import seaborn as sns


# Replace the provider URL with your desired Ethereum node URL (e.g., Infura or your local node).
provider_url = "https://mainnet.infura.io/v3/68fc3da0eff84bd2a07f267adeca7b1e"
web3 = Web3(Web3.HTTPProvider(provider_url))


#block_start = 12710000

#block_end = 12730000

block_start = 19426581

block_end = 19426591

london_fork = 12965000






block_interval = block_end - block_start

##block_interval = 10

is_FBB_tx = set()
FBB_eth_sent_to_fee_recipient = [0] * block_interval
FBB_gas_fee = [0] * block_interval
non_FBB_gas_fee = [0] * block_interval
static_reward = [0] * block_interval
uncle_incl_reward = [0] * block_interval

fee_recipient_eth_diff = [0] * block_interval
sum_MaxFeePerGas_Bundle = [0] * block_interval



def set_block_interval(start, end):
    global block_start, block_end, block_interval
    global is_FBB_tx, FBB_eth_sent_to_fee_recipient, FBB_gas_fee, non_FBB_gas_fee, static_reward, uncle_incl_reward
    block_start = start
    block_end = end
    block_interval = block_end - block_start
    is_FBB_tx = set()
    FBB_eth_sent_to_fee_recipient = [0] * block_interval
    FBB_gas_fee = [0] * block_interval
    non_FBB_gas_fee = [0] * block_interval
    static_reward = [0] * block_interval
    uncle_incl_reward = [0] * block_interval
    FBB_sum_MaxFeePerGas = [0] * block_interval



def calc_FBB():
    print('begin calc_FBB')
    global is_FBB_tx, FBB_eth_sent_to_fee_recipient, FBB_gas_fee, non_FBB_gas_fee, static_reward, uncle_incl_reward
    header = {
        'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    }

    blockno = block_end
  while blockno > block_start:
        print('blockno =', blockno)
        url = 'https://blocks.flashbots.net/v1/blocks'
        content = requests.get(url,
                               params={
                                   'before': str(blockno),
                                   'limit': '4'
                               }).text
        true = True
        false = False
        null = None
        mp = eval(content)
        if mp['blocks'] == []: break
        for block in mp['blocks']:
            #modified because Flashbots API is changed
            thisblockno = block['block_number']
            if thisblockno < block_start: continue
            blockno = min(blockno, thisblockno)

            FBB_eth_sent_to_fee_recipient[thisblockno - block_start] = int(
                block['eth_sent_to_fee_recipient'])
            FBB_gas_fee[thisblockno - block_start] = int(
                block['miner_reward']) - int(block['eth_sent_to_fee_recipient'])
            for tx in block['transactions']:
                txhash = HexBytes(tx['transaction_hash'])
                is_FBB_tx.add(txhash)
    print('end calc_FBB')



def calc_basic():
    print('begin calc_basic')
    global is_FBB_tx, FBB_eth_sent_to_fee_recipient, FBB_gas_fee, non_FBB_gas_fee, static_reward, uncle_incl_reward
    for blockno in range(block_start, block_end):
        print('blockno =', blockno)
        block_info = web3.eth.get_block(blockno,full_transactions=True)
        #block_info = web3_api.get_block_info(blockno)


        if blockno < 7280000:
            assert (
                0
            )  #Constantinople fork, changing the static reward from 3 eth to 2 eth
        static_reward[blockno - block_start] = 2 * 10**18
        uncle_incl_reward[blockno - block_start] = len(
            block_info['uncles']) * 625 * 10**14

        basefee = 0
        if 'baseFeePerGas' in block_info:
            if type(block_info['baseFeePerGas']) == str:
                basefee = int(block_info['baseFeePerGas'], 16)
            elif type(block_info['baseFeePerGas']) == int:
                basefee = block_info['baseFeePerGas']
        sum = 0
        FBB_sum = 0
        for tx in block_info['transactions']:
            txhash = HexBytes(tx.hash)
            #txhash = HexBytes(tx['transaction_hash'])


            txtype = HexBytes(tx['type'])
            recepit = web3.eth.get_transaction_receipt(txhash)
            #recepit = web3_api.get_tx_receipt(txhash)
            tx_gasfee = 0
            if txtype == HexBytes('0x0') or txtype == HexBytes('0x1'):
                assert (type(tx['gasPrice']) == int)
                assert (type(recepit['gasUsed']) == int)
                tx_gasfee = (tx['gasPrice'] - basefee) * recepit['gasUsed']
            elif txtype == HexBytes('0x2'):
                maxPriorityFeePerGas = tx['maxPriorityFeePerGas']
                if type(maxPriorityFeePerGas) == str:
                    maxPriorityFeePerGas = int(maxPriorityFeePerGas, 16)
                maxFeePerGas = tx['maxFeePerGas']
                if type(maxFeePerGas) == str:
                    maxFeePerGas = int(maxFeePerGas, 16)
                tx_gasfee = min(maxPriorityFeePerGas,
                                maxFeePerGas - basefee) * recepit['gasUsed']
            else:
                print('txtype =', txtype)
                print('txhash =', txhash.hex())
                print(tx)
                assert (0)
            sum += tx_gasfee
            FBB_sum += tx_gasfee if txhash in is_FBB_tx else 0
            FBB_sum_MaxFeePerGas += tx['maxFeePerGas'] if txhash in is_FBB_tx else 0


            # Calculate fee_recipient_eth_diff for each block
            #fee_recipient_eth_diff[blockno - block_start] = FBB_gas_fee[blockno - block_start] \
            #                                                + FBB_eth_sent_to_fee_recipient[blockno - block_start]

            # Calculate sumFeeCapBundle for each block
            sum_fee_cap = 0
            for tx in block_info['transactions']:
                txhash = HexBytes(tx.hash)
                if txhash in is_FBB_tx:
                    # Fetch maxFeePerGas for each FBB transaction
                    tx_data = web3.eth.get_transaction(txhash)
                    if 'maxFeePerGas' in tx_data:
                        max_fee_per_gas = int(tx_data['maxFeePerGas'], 16)
                        sum_fee_cap += max_fee_per_gas
            FBB_sum_MaxFeePerGas[blockno - block_start] = sum_fee_cap

        #assert(FBB_sum == FBB_gas_fee[blockno-block_start]) usually is, but for miners tx, flashbots remove the gas from calculating
        FBB_gas_fee[blockno - block_start] = FBB_sum
        non_FBB_gas_fee[blockno - block_start] = sum - FBB_sum
    print('end calc_basic')





def MEVdata_to_csv(stepsize: int):
    writer = csv.writer(open('./MEVfig/MEVdata.csv', 'w', newline=''))
    writer.writerow(('block_number', 'FBB_eth_sent_to_fee_recipient', 'FBB_gas_fee',
                     'non_FBB_gas_fee', 'static_reward', 'uncle_incl_reward'))
    for start in range(block_start, block_end, stepsize):
        print(start)
        end = min(start + stepsize, block_end)
        file_prefix = './MEVdata/[%d,%d)' % (start, end)
        FBB_coinbase_transfer = read_list(file_prefix +
                                          'FBB_eth_sent_to_fee_recipient.txt')
        FBB_gas_fee = read_list(file_prefix + 'FBB_gas_fee.txt')
        non_FBB_gas_fee = read_list(file_prefix + 'non_FBB_gas_fee.txt')
        static_reward = read_list(file_prefix + 'static_reward.txt')
        uncle_incl_reward = read_list(file_prefix + 'uncle_incl_reward.txt')
        for blockno in range(start, end):
            #if blockno<12865000 or blockno>=13135000: continue
            id = blockno - start
            writer.writerow((blockno, FBB_eth_sent_to_fee_recipient[id],
                             FBB_gas_fee[id], non_FBB_gas_fee[id],
                             static_reward[id], uncle_incl_reward[id]))






if __name__ == '__main__':
    #f=open('tmp.txt','w')
    #print(web3_api.get_block_info(8364113,detail=False),file=f)
    #txhash = HexBytes('0x1c1281d2c858a2afcb50bc1df66a0d55aae692a5506ef66b3d4083c64b50f54d')
    #print(web3_api.get_tx_info(txhash),file =f)
    if len(sys.argv) == 1:
        print('Need at least one option: --data / --csv / --img')
        exit(0)
    elif len(sys.argv) == 4:
        set_block_interval(int(sys.argv[2]), int(sys.argv[3]))
    elif len(sys.argv) != 2:
        print('need 0 or 2 arguments [start,end)')
        exit(0)

    option = sys.argv[1]
    if option == '--data':
        calc_FBB()
        calc_basic()

        file_prefix = './MEVdata/[%d,%d)' % (block_start, block_end)
        write_list(FBB_eth_sent_to_fee_recipient,
                   file_prefix + 'FBB_eth_sent_to_fee_recipient.txt')
        write_list(FBB_gas_fee, file_prefix + 'FBB_gas_fee.txt')
        write_list(non_FBB_gas_fee, file_prefix + 'non_FBB_gas_fee.txt')
        write_list(static_reward, file_prefix + 'static_reward.txt')
        write_list(uncle_incl_reward, file_prefix + 'uncle_incl_reward.txt')
    elif option == '--csv':
        MEVdata_to_csv(20000)
  #  elif option == '--img':
   #     csv_to_img()
    #elif option == '--test':
     #   csv_distr_test()
    else:
        print('unknown option')
        exit(0)