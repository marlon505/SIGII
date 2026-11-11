import bcrypt

password = "indiana25*"
hash_generado = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
print(hash_generado.decode())