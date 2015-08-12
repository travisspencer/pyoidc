# pylint: disable=missing-docstring,no-self-use

import base64
import os

from jwkest.jwk import SYMKey, rsa_load
from jwkest.jws import JWS

from jwkest.jwt import JWT
import pytest

from oic.oauth2 import Client
from oic.oauth2.grant import Grant
from oic.oauth2.message import AccessTokenRequest, ResourceRequest, \
    AuthorizationResponse, AccessTokenResponse
from oic.oic import JWT_BEARER
from oic.utils.authn.client import ClientSecretBasic, BearerHeader, BearerBody, \
    ClientSecretPost, PrivateKeyJWT, ClientSecretJWT
from utils_for_tests import _eq  # pylint: disable=import-error
from oic.utils.keyio import KeyBundle


@pytest.fixture
def client():
    cli = Client("A")
    cli.client_secret = "boarding pass"
    return cli


class TestClientSecretBasic(object):
    def test_construct(self, client):
        cis = AccessTokenRequest(code="foo", redirect_uri="http://example.com")

        csb = ClientSecretBasic(client)
        http_args = csb.construct(cis)

        assert http_args == {"headers": {"Authorization": "Basic {}".format(
            base64.b64encode("A:boarding pass".encode("utf-8")).decode(
                "utf-8"))}}


class TestBearerHeader(object):
    def test_construct(self, client):
        request_args = {"access_token": "Sesame"}
        bh = BearerHeader(client)
        http_args = bh.construct(request_args=request_args)

        assert http_args == {"headers": {"Authorization": "Bearer Sesame"}}

    def test_construct_with_http_args(self, client):
        request_args = {"access_token": "Sesame"}
        bh = BearerHeader(client)
        http_args = bh.construct(request_args=request_args,
                                 http_args={"foo": "bar"})

        assert _eq(http_args.keys(), ["foo", "headers"])
        assert http_args["headers"] == {"Authorization": "Bearer Sesame"}

    def test_construct_with_headers(self, client):
        request_args = {"access_token": "Sesame"}

        bh = BearerHeader(client)
        http_args = bh.construct(request_args=request_args,
                                 http_args={"headers": {"x-foo": "bar"}})

        assert _eq(http_args.keys(), ["headers"])
        assert _eq(http_args["headers"].keys(), ["Authorization", "x-foo"])
        assert http_args["headers"]["Authorization"] == "Bearer Sesame"

    def test_construct_with_resource_request(self, client):
        bh = BearerHeader(client)
        cis = ResourceRequest(access_token="Sesame")

        http_args = bh.construct(cis)

        assert "access_token" not in cis
        assert http_args == {"headers": {"Authorization": "Bearer Sesame"}}

    def test_construct_with_token(self, client):
        resp1 = AuthorizationResponse(code="auth_grant", state="state")
        client.parse_response(AuthorizationResponse, resp1.to_urlencoded(),
                              "urlencoded")
        resp2 = AccessTokenResponse(access_token="token1",
                                    token_type="Bearer", expires_in=0,
                                    state="state")
        client.parse_response(AccessTokenResponse, resp2.to_urlencoded(),
                              "urlencoded")

        http_args = BearerHeader(client).construct(ResourceRequest(),
                                                   state="state")
        assert http_args == {"headers": {"Authorization": "Bearer token1"}}


class TestBearerBody(object):
    def test_construct_with_request_args(self, client):
        request_args = {"access_token": "Sesame"}
        cis = ResourceRequest()
        http_args = BearerBody(client).construct(cis, request_args)

        assert cis["access_token"] == "Sesame"
        assert http_args is None

    def test_construct_with_state(self, client):
        resp = AuthorizationResponse(code="code", state="state")
        grant = Grant()
        grant.add_code(resp)
        atr = AccessTokenResponse(access_token="2YotnFZFEjr1zCsicMWpAA",
                                  token_type="example",
                                  refresh_token="tGzv3JOkF0XG5Qx2TlKWIA",
                                  example_parameter="example_value",
                                  scope=["inner", "outer"])
        grant.add_token(atr)
        client.grant["state"] = grant

        cis = ResourceRequest()
        http_args = BearerBody(client).construct(cis, {}, state="state",
                                                 scope="inner")
        assert cis["access_token"] == "2YotnFZFEjr1zCsicMWpAA"
        assert http_args is None

    def test_construct_with_request(self, client):
        resp1 = AuthorizationResponse(code="auth_grant", state="state")
        client.parse_response(AuthorizationResponse, resp1.to_urlencoded(),
                              "urlencoded")
        resp2 = AccessTokenResponse(access_token="token1",
                                    token_type="Bearer", expires_in=0,
                                    state="state")
        client.parse_response(AccessTokenResponse, resp2.to_urlencoded(),
                              "urlencoded")

        cis = ResourceRequest()
        BearerBody(client).construct(cis, state="state")

        assert "access_token" in cis
        assert cis["access_token"] == "token1"


class TestClientSecretPost(object):
    def test_construct(self, client):
        cis = AccessTokenRequest(code="foo", redirect_uri="http://example.com")
        csp = ClientSecretPost(client)
        http_args = csp.construct(cis)

        assert cis["client_id"] == "A"
        assert cis["client_secret"] == "boarding pass"
        assert http_args is None

        cis = AccessTokenRequest(code="foo", redirect_uri="http://example.com")
        http_args = csp.construct(cis, {},
                                  http_args={"client_secret": "another"})
        assert cis["client_id"] == "A"
        assert cis["client_secret"] == "another"
        assert http_args == {}


class TestPrivateKeyJWT(object):
    def test_construct(self, client):
        base_path = os.path.join(os.path.dirname(__file__), os.pardir,
                                 os.pardir, os.pardir, "data/keys")
        _key = rsa_load(
            os.path.join(base_path, "rsa.key"))
        kc_rsa = KeyBundle([{"key": _key, "kty": "RSA", "use": "ver"},
                            {"key": _key, "kty": "RSA", "use": "sig"}])
        client.keyjar[""] = kc_rsa
        client.token_endpoint = "https://example.com/token"

        cis = AccessTokenRequest()
        pkj = PrivateKeyJWT(client)
        http_args = pkj.construct(cis, algorithm="RS256")
        assert http_args == {}
        cas = cis["client_assertion"]
        _jwt = JWT().unpack(cas)
        jso = _jwt.payload()
        assert _eq(jso.keys(), ["aud", "iss", "sub", "jti", "exp", "iat"])
        assert _jwt.headers == {'alg': 'RS256'}


class TestClientSecretJWT(object):
    def test_client_secret_jwt(self, client):
        client.token_endpoint = "https://example.com/token"

        csj = ClientSecretJWT(client)
        cis = AccessTokenRequest()

        http_args = csj.construct(cis, algorithm="HS256")
        assert cis["client_assertion_type"] == JWT_BEARER
        assert "client_assertion" in cis
        cas = cis["client_assertion"]
        _jwt = JWT().unpack(cas)
        jso = _jwt.payload()
        assert _eq(jso.keys(), ["aud", "iss", "sub", "jti", "exp", "iat"])
        assert _jwt.headers == {'alg': 'HS256'}

        _rj = JWS()
        info = _rj.verify_compact(cas, [SYMKey(key=client.client_secret)])

        assert _eq(info.keys(), ["aud", "iss", "sub", "jti", "exp", "iat"])
