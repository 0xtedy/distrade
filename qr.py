import qrcode
def get_qrcode(data): #pour generer le QR code à partir de l'ID 
  QRCodefile = data+".png"
  QRcode = qrcode.make(data)
  QRcode.save(QRCodefile)
  print("saved as",QRCodefile)