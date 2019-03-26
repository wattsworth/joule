from OpenSSL import crypto
import secrets

def issue_cert(name, ca_cert, ca_key):
    # generate a key
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)
    # generate a signed certificate

    cert = crypto.X509()
    cert.get_subject().CN = name
    cert.set_serial_number(secrets.randbits(128))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(5 * 365 * 24 * 60 * 60)  # 5 years
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(ca_key, 'sha256')
    with open("%s_%s.crt" % (name, ca_cert.get_subject().CN), "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open("%s.key" % name, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    return cert, k


def make_ca(name):
    # generate a key
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)
    # generate a self signed certificate

    cert = crypto.X509()
    cert.get_subject().CN = name
    cert.set_serial_number(secrets.randbits(128))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(5 * 365 * 24 * 60 * 60)  # 5 years
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')
    with open("%s_self_signed.crt" % name, "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open("%s.key" % name, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    return cert, k
