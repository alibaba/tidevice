# coding: utf-8
#
# Referenced from
# - https://github.com/YueChen-C/py-ios-device/blob/10d207c329ae56e25267d5b7386cf551676443b4/ios_device/util/ssl.py
# - https://github.com/anonymous5l/iConsole/blob/dc65f76183feff0d9d897d8506fd70603838da81/tunnel/lockdown.go#L29

__all__ = ['make_certs_and_key']

import base64
from datetime import datetime, timedelta

from OpenSSL.crypto import FILETYPE_PEM as PEM
from OpenSSL.crypto import (TYPE_RSA, X509, PKey, X509Req, dump_certificate,
                            dump_privatekey, load_publickey)
from pyasn1.codec.der import decoder as der_decoder
from pyasn1.codec.der import encoder as der_encoder
from pyasn1.type import univ


def make_certs_and_key(device_public_key: bytes):
    """
    1. create private key
    2. create certificate
    """
    device_key = load_publickey(PEM, convert_PKCS1_to_PKCS8_pubkey(device_public_key))
    device_key._only_public = False

    # root key
    root_key = PKey()
    root_key.generate_key(TYPE_RSA, 2048)

    host_req = make_req(root_key)
    host_cert = make_cert(host_req, root_key)

    device_req = make_req(device_key, 'Device')
    device_cert = make_cert(device_req, root_key)

    return dump_certificate(PEM, host_cert), dump_privatekey(PEM, root_key), dump_certificate(PEM, device_cert)


def convert_PKCS1_to_PKCS8_pubkey(data: bytes) -> bytes:
    pubkey_pkcs1_b64 = b''.join(data.split(b'\n')[1:-2])
    pubkey_pkcs1, restOfInput = der_decoder.decode(base64.b64decode(pubkey_pkcs1_b64))
    bit_str = univ.Sequence()
    bit_str.setComponentByPosition(0, univ.Integer(pubkey_pkcs1[0]))
    bit_str.setComponentByPosition(1, univ.Integer(pubkey_pkcs1[1]))
    bit_str = der_encoder.encode(bit_str)
    try:
        bit_str = ''.join([('00000000'+bin(ord(x))[2:])[-8:] for x in list(bit_str)])
    except Exception:
        bit_str = ''.join([('00000000'+bin(x)[2:])[-8:] for x in list(bit_str)])
    bit_str = univ.BitString("'%s'B" % bit_str)
    pubkeyid = univ.Sequence()
    pubkeyid.setComponentByPosition(0, univ.ObjectIdentifier('1.2.840.113549.1.1.1'))  # == OID for rsaEncryption
    pubkeyid.setComponentByPosition(1, univ.Null(''))
    pubkey_seq = univ.Sequence()
    pubkey_seq.setComponentByPosition(0, pubkeyid)
    pubkey_seq.setComponentByPosition(1, bit_str)
    pubkey = der_encoder.encode(pubkey_seq)
    return b'-----BEGIN PUBLIC KEY-----\n' + base64.encodebytes(pubkey) + b'-----END PUBLIC KEY-----\n'


def x509_time(**kwargs) -> bytes:
    dt = datetime.utcnow() + timedelta(**kwargs)
    return dt.strftime('%Y%m%d%H%M%SZ').encode('utf-8')


def make_cert(req: X509Req, ca_pkey: PKey) -> X509:
    cert = X509()
    cert.set_serial_number(1)
    cert.set_version(2)
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.set_notBefore(x509_time(minutes=-1))
    cert.set_notAfter(x509_time(days=30))
    # noinspection PyTypeChecker
    cert.sign(ca_pkey, 'sha256')
    return cert


def make_req(pub_key, cn=None, digest=None) -> X509Req:
    req = X509Req()
    req.set_version(2)
    req.set_pubkey(pub_key)
    if cn is not None:
        subject = req.get_subject()
        subject.CN = cn.encode('utf-8')
    if digest:
        req.sign(pub_key, digest)
    return req
