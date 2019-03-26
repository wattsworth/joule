import asyncio
import aiohttp
import socket
import ssl


async def main():

    context = ssl.create_default_context()
    context.load_verify_locations(cafile="server_self_signed.crt")
    context.load_cert_chain(certfile="client2_self_signed.crt", keyfile="client2.key")
    context.load_cert_chain(certfile="client_server.crt", keyfile="client.key")
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False

    async with aiohttp.ClientSession() as session:
        async with session.get('https://localhost:8443', ssl=context) as resp:
            print(resp.status)
            print(await resp.text())
    return

    with socket.create_connection(("localhost", 8443)) as sock:
        with context.wrap_socket(sock) as ssock:
            data = ssock.recv(100)
            print(data.decode("utf-8"))
            print(ssock.getpeercert(False))
    return

    pass

if __name__=="__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
