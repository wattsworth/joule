import ssl
import io
import cert
import socket
from OpenSSL import crypto

from aiohttp import web

async def hello(request):
    return web.Response(text="This is encrypte")

def main():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='server_self_signed.crt',
                            keyfile='server.key')
    context.load_verify_locations(cafile="server_self_signed.crt")
    context.verify_mode = ssl.CERT_REQUIRED
    app = web.Application()
    app.add_routes([web.get('/', hello)])
    web.run_app(app, ssl_context=context)
    return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
        sock.bind(('127.0.0.1', 8443))
        sock.listen(5)
        with context.wrap_socket(sock, server_side=True) as ssock:
            conn, addr = ssock.accept()
            print("got a connection from ", addr)
            conn.sendall("Hello world".encode("utf-8"))


def alt_main():
    cert1, k1 = cert.make_cert("server1")
    cadata = (crypto.dump_privatekey(crypto.FILETYPE_PEM, k1).decode("ascii") + "\n" +
              crypto.dump_certificate(crypto.FILETYPE_PEM, cert1).decode("ascii"))
    print(cadata)
    #ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #ctx.
    ctx = ssl.SSLContext()
    #ctx.load_verify_locations(cadata=cadata)
    ctx.verify_mode = ssl.CERT_OPTIONAL
    #ctx.set_ciphers("ECDHE-RSA-AES256-GCM-SHA384")

    print(len(ctx.get_ciphers()))
    for cipher in ctx.get_ciphers():
        print(cipher['name'])
    #print(ctx.get_ciphers())

    app = web.Application()
    app.add_routes([web.get('/', hello)])
    web.run_app(app, ssl_context=ctx)



if __name__ == "__main__":
    main()
