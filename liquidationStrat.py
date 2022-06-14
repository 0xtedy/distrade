from web3 import Web3
import abi
import const
import time
import asyncio

polygon = "https://polygon-rpc.com/"
web3 = Web3(Web3.HTTPProvider(polygon))
MAIAddress = Web3.toChecksumAddress('0xa3fa99a148fa48d14ed51d610c367c61876997f1')

RouterAddress = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
vaultRouterAddressWETH = '0x3fd939B017b31eaADF9ae50C7fF7Fa5c0661d47C'
klimaDAO = Web3.toChecksumAddress("0x65A5076C0BA74e5f3e069995dc3DAB9D197d995c")

# vérification de la liquidabilité d'une position
def checkLiquidation(_vaultID, _vaultAddress):
    vault_contract = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    return vault_contract.functions.checkLiquidation(_vaultID).call()

# retourne le collateral d'une position
def getCollateral(_vaultAddress):
    vault_contract = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    return vault_contract.functions.collateral().call()

# retourne le prix du gas
def getGasPrice():
    gasPrice = web3.eth.gas_price
    return gasPrice*10**-9

#retourne la solde d'un addresse
def getBalance(_tokenAddress, _pblAddress):
    token_contract = web3.eth.contract(address=_tokenAddress, abi=abi.erc20ABI)
    return token_contract.functions.balanceOf(_pblAddress).call()

# verifie le niveau d'approval
def getApproval(_vaultAddress, _pblAddress, _tokenAddress):
    vault_contract = web3.eth.contract(address=_tokenAddress, abi=abi.erc20ABI)
    return vault_contract.functions.allowance(_pblAddress, _vaultAddress).call()

#compte le nombre de vault
def vaultCount(_vaultAddress):
    vault_contract = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    return vault_contract.functions.vaultCount().call()

#retourne la dette d'un vault
def vaultDebt(_vaultID, _vaultAddress):
    vault_contract = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    return vault_contract.functions.vaultDebt(_vaultID).call()

#retourne la dette d'un vault
def checkRatio(_vaultID, _vaultAddress):
    vault_contract = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    return vault_contract.functions.checkCollateralPercentage(_vaultID).call()


# analyse les positions liquidables
def findRiskyVault(_vaultAddress):
    riskyvaults = []
    vault_contract = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    print("looking for risky vault 👀",vaultCount(_vaultAddress),"left")
    for id in range(1, vaultCount(_vaultAddress)):
        try:
            if checkLiquidation(id, _vaultAddress) == True and checkRatio(id, _vaultAddress) != 0:
                print(id)
                print("Vault liquidable with",vaultDebt(id, _vaultAddress)*10**-18,"usd")
                riskyvaults.append([id, vaultDebt(id, _vaultAddress)*10**-18])
        except Exception as e:
            print("Error", e.__class__, "occurred.")
    return riskyvaults

ls = [const.MAIVaultAddressWETH[0], const.MAIVaultAddressGHST[0], const.MAIVaultAddressBAL[0],  const.MAIVaultAddressCRV[0],  const.MAIVaultAddressBTC[0]]
ns = [const.MAIVaultAddressWETH[1], const.MAIVaultAddressGHST[1], const.MAIVaultAddressBAL[1],  const.MAIVaultAddressCRV[1],  const.MAIVaultAddressBTC[1]]
lis = {}

async def runStratLiquidation():
    for x in range(len(ls)):
        lis[ns[x]] = findRiskyVault(ls[x])
    
    # lis[ns[2]] = findRiskyVault(ls[2])
    
    for x in lis["BAL"]:
        if checkLiquidation(x, ls[2]) == True:
            print("Vault liquidable with",vaultDebt(x, ls[2])*10**-18,"usd")
          
    print(lis)
    return lis
    
# liquide le vault choisie
def liquidateVault(_vaultAddress, _vaultId, _pblAddress, _prvKey):
    gas = getGasPrice()+5
    assert(gas<120)
    token = getCollateral(_vaultAddress)
    initialBalance = getBalance(MAIAddress, _pblAddress)
    _pblAddress = Web3.toChecksumAddress(_pblAddress)
    contractAddress = web3.eth.contract(address=_vaultAddress, abi=abi.MAIvaultABI)
    approveToken(_vaultAddress, MAIAddress, _pblAddress, _prvKey)
    approveToken(RouterAddress, token, _pblAddress, _prvKey)
    trx = contractAddress.functions.liquidateVault(_vaultId).buildTransaction({
            'from': _pblAddress,
            'gas': 250000,
            'gasPrice': web3.toWei(gas,'gwei'),
            'nonce': web3.eth.get_transaction_count(_pblAddress),
            })
    
    signed_trx = web3.eth.account.sign_transaction(trx, private_key=_prvKey)
    trx_token = web3.eth.send_raw_transaction(signed_trx.rawTransaction)
    print("transaction => https://polygonscan.com/tx/"+web3.toHex(trx_token))
  
    trx = contractAddress.functions.getPaid().buildTransaction({
            'from': _pblAddress,
            'gas': 250000,
            'gasPrice': web3.toWei(gas,'gwei'),
            'nonce': web3.eth.get_transaction_count(_pblAddress)+1,
            })
    
    signed_trx = web3.eth.account.sign_transaction(trx, private_key=_prvKey)
    trx_token = web3.eth.send_raw_transaction(signed_trx.rawTransaction)
    print("transaction => https://polygonscan.com/tx/"+web3.toHex(trx_token))
    time.sleep(20)
    router_contract = web3.eth.contract(address=RouterAddress, abi=abi.routerABI)
    amount = getBalance(token, _pblAddress)
    gas = getGasPrice()+5
    trx = router_contract.functions.swapExactTokensForTokens(
    amount,
    0, 
    [token,MAIAddress],
    _pblAddress,
    (int(time.time()) + 10000)
    ).buildTransaction({
    'from': _pblAddress,
    'gas': 250000,
    'gasPrice': web3.toWei(gas+5,'gwei'),
    'nonce': web3.eth.get_transaction_count(_pblAddress),
    })

    signed_trx = web3.eth.account.sign_transaction(trx, private_key=_prvKey)
    trx_token = web3.eth.send_raw_transaction(signed_trx.rawTransaction)
    print("selling rewards")
    print("transaction => https://polygonscan.com/tx/"+web3.toHex(trx_token))
    time.sleep(10)
    amountEarned = getBalance(MAIAddress, _pblAddress)-initialBalance
    msg = "You earned "+str(amountEarned*10**-18)+" USD !"
    return msg

# autorise un contrat à depenser un token
def approveToken(_vaultAddress ,_token, _pblAddress, _prvKey):
    approved = getApproval(_vaultAddress, _pblAddress, _token)
    gas = getGasPrice()+5
    if approved == 0:
      print("approving token (~10sec)")
      erc20_contract = web3.eth.contract(address=_token, abi=abi.erc20ABI)
      trx = erc20_contract.functions.approve(_vaultAddress, 8000000000000000000000000000).buildTransaction({
              'from': _pblAddress,
              'gas': 50000,
              'gasPrice': web3.toWei(gas,'gwei'),
              'nonce': web3.eth.get_transaction_count(_pblAddress),
              })
      signed_trx = web3.eth.account.sign_transaction(trx, private_key=_prvKey)
      trx_token = web3.eth.send_raw_transaction(signed_trx.rawTransaction)
      print("transaction => https://polygonscan.com/tx/"+web3.toHex(trx_token))
      time.sleep(10)


# envoie de l'argent à la klima dao
def donateCharity(_amount, _token, _pblAddress, _prvKey):
    erc20_contract = web3.eth.contract(address=_token, abi=abi.erc20ABI)
    gas = getGasPrice()+5
    trx = erc20_contract.functions.transfer(klimaDAO, int(_amount*10**18)).buildTransaction({
              'from': _pblAddress,
              'gas': 90000,
              'gasPrice': web3.toWei(gas,'gwei'),
              'nonce': web3.eth.get_transaction_count(_pblAddress),
              })
    signed_trx = web3.eth.account.sign_transaction(trx, private_key=_prvKey)
    trx_token = web3.eth.send_raw_transaction(signed_trx.rawTransaction)
    print("transaction => https://polygonscan.com/tx/"+web3.toHex(trx_token))
