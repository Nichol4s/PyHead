
import t
from textwrap import dedent

def test_001():
    tests = t.request("001.http", {
        "method": "PUT",
        "uri": t.uri("/stuff/here?foo=bar"),
        "version": (1, 0),
        "headers": [
            ("Server", "http://127.0.0.1:5984"),
            ("Content-Type", "application/json"),
            ("Content-Length", "14")
        ],
        "body": '{"nom": "nom"}'
    })
    for case in tests.gen_cases():
        yield case

def test_002():
    tests = t.request("002.http", {
        "method": "GET",
        "uri": t.uri("/test"),
        "version": (1, 1),
        "headers": [
            ("User-Agent", "curl/7.18.0 (i486-pc-linux-gnu) libcurl/7.18.0 OpenSSL/0.9.8g zlib/1.2.3.3 libidn/1.1"),
            ("Host", "0.0.0.0=5000"),
            ("Accept", "*/*")
        ],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_003():
    tests = t.request("003.http", {
        "method": "GET",
        "uri": t.uri("/favicon.ico"),
        "version": (1, 1),
        "headers": [
            ("Host", "0.0.0.0=5000"),
            ("User-Agent", "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9) Gecko/2008061015 Firefox/3.0"),
            ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            ("Accept-Language", "en-us,en;q=0.5"),
            ("Accept-Encoding", "gzip,deflate"),
            ("Accept-Charset", "ISO-8859-1,utf-8;q=0.7,*;q=0.7"),
            ("Keep-Alive", "300"),
            ("Connection", "keep-alive")
        ],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_004():
    tests = t.request("004.http", {
        "method": "GET",
        "uri": t.uri("/silly"),
        "version": (1, 1),
        "headers": [
            ("aaaaaaaaaaaaa", "++++++++++")
        ],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_005():
    tests = t.request("005.http", {
        "method": "GET",
        "uri": t.uri("/forums/1/topics/2375?page=1#posts-17408"),
        "version": (1, 1),
        "headers": [],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_006():
    tests = t.request("006.http", {
        "method": "GET",
        "uri": t.uri("/get_no_headers_no_body/world"),
        "version": (1, 1),
        "headers": [],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_007():
    tests = t.request("007.http", {
        "method": "GET",
        "uri": t.uri("/get_one_header_no_body"),
        "version": (1, 1),
        "headers": [
            ("Accept", "*/*")
        ],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_008():
    tests = t.request("008.http", {
        "method": "GET",
        "uri": t.uri("/unusual_content_length"),
        "version": (1, 0),
        "headers": [
            ("conTENT-Length", "5")
        ],
        "body": "HELLO"
    })
    for case in tests.gen_cases():
        yield case

def test_009():
    tests = t.request("009.http", {
        "method": "POST",
        "uri": t.uri("/post_identity_body_world?q=search#hey"),
        "version": (1, 1),
        "headers": [
            ("Accept", "*/*"),
            ("Transfer-Encoding", "identity"),
            ("Content-Length", "5")
        ],
        "body": "World"
    })
    for case in tests.gen_cases():
        yield case

def test_010():
    tests = t.request("010.http", {
        "method": "POST",
        "uri": t.uri("/post_chunked_all_your_base"),
        "version": (1, 1),
        "headers": [
            ("Transfer-Encoding", "chunked"),
        ],
        "body": "all your base are belong to us"
    })
    for case in tests.gen_cases():
        yield case

def test_011():
    tests = t.request("011.http", {
        "method": "POST",
        "uri": t.uri("/two_chunks_mult_zero_end"),
        "version": (1, 1),
        "headers": [
            ("Transfer-Encoding", "chunked")
        ],
        "body": "hello world"
    })
    for case in tests.gen_cases():
        yield case

def test_012():
    tests = t.request("012.http", {
        "method": "POST",
        "uri": t.uri("/chunked_w_trailing_headers"),
        "version": (1, 1),
        "headers": [
            ("Transfer-Encoding", "chunked")
        ],
        "body": "hello world",
        "trailers": [
            ("Vary", "*"),
            ("Content-Type", "text/plain")
        ]
    })
    for case in tests.gen_cases():
        yield case

def test_013():
    tests = t.request("013.http", {
        "method": "POST",
        "uri": t.uri("/chunked_w_extensions"),
        "version": (1, 1),
        "headers": [
            ("Transfer-Encoding", "chunked")
        ],
        "body": "hello world."
    })
    for case in tests.gen_cases():
        yield case

def test_014():
    tests = t.request("014.http", {
        "method": "GET",
        "uri": t.uri('/with_"quotes"?foo="bar"'),
        "version": (1, 1),
        "headers": [],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_015():
    tests = t.request("015.http", {
        "method": "GET",
        "uri": t.uri("/test"),
        "version": (1, 0),
        "headers": [
            ("Host", "0.0.0.0:5000"),
            ("User-Agent", "ApacheBench/2.3"),
            ("Accept", "*/*")
        ],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case

def test_016():
    certificate = """-----BEGIN CERTIFICATE-----\r\n
    MIIFbTCCBFWgAwIBAgICH4cwDQYJKoZIhvcNAQEFBQAwcDELMAkGA1UEBhMCVUsx\r\n
    ETAPBgNVBAoTCGVTY2llbmNlMRIwEAYDVQQLEwlBdXRob3JpdHkxCzAJBgNVBAMT\r\n
    AkNBMS0wKwYJKoZIhvcNAQkBFh5jYS1vcGVyYXRvckBncmlkLXN1cHBvcnQuYWMu\r\n
    dWswHhcNMDYwNzI3MTQxMzI4WhcNMDcwNzI3MTQxMzI4WjBbMQswCQYDVQQGEwJV\r\n
    SzERMA8GA1UEChMIZVNjaWVuY2UxEzARBgNVBAsTCk1hbmNoZXN0ZXIxCzAJBgNV\r\n
    BAcTmrsogriqMWLAk1DMRcwFQYDVQQDEw5taWNoYWVsIHBhcmQYJKoZIhvcNAQEB\r\n
    BQADggEPADCCAQoCggEBANPEQBgl1IaKdSS1TbhF3hEXSl72G9J+WC/1R64fAcEF\r\n
    W51rEyFYiIeZGx/BVzwXbeBoNUK41OK65sxGuflMo5gLflbwJtHBRIEKAfVVp3YR\r\n
    gW7cMA/s/XKgL1GEC7rQw8lIZT8RApukCGqOVHSi/F1SiFlPDxuDfmdiNzL31+sL\r\n
    0iwHDdNkGjy5pyBSB8Y79dsSJtCW/iaLB0/n8Sj7HgvvZJ7x0fr+RQjYOUUfrePP\r\n
    u2MSpFyf+9BbC/aXgaZuiCvSR+8Snv3xApQY+fULK/xY8h8Ua51iXoQ5jrgu2SqR\r\n
    wgA7BUi3G8LFzMBl8FRCDYGUDy7M6QaHXx1ZWIPWNKsCAwEAAaOCAiQwggIgMAwG\r\n
    1UdEwEB/wQCMAAwEQYJYIZIAYb4QgHTTPAQDAgWgMA4GA1UdDwEB/wQEAwID6DAs\r\n
    BglghkgBhvhCAQ0EHxYdVUsgZS1TY2llbmNlIFVzZXIgQ2VydGlmaWNhdGUwHQYD\r\n
    VR0OBBYEFDTt/sf9PeMaZDHkUIldrDYMNTBZMIGaBgNVHSMEgZIwgY+AFAI4qxGj\r\n
    loCLDdMVKwiljjDastqooXSkcjBwMQswCQYDVQQGEwJVSzERMA8GA1UEChMIZVNj\r\n
    aWVuY2UxEjAQBgNVBAsTCUF1dGhvcml0eTELMAkGA1UEAxMCQ0ExLTArBgkqhkiG\r\n
    9w0BCQEWHmNhLW9wZXJhdG9yQGdyaWQtc3VwcG9ydC5hYy51a4IBADApBgNVHRIE\r\n
    IjAggR5jYS1vcGVyYXRvckBncmlkLXN1cHBvcnQuYWMudWswGQYDVR0gBBIwEDAO\r\n
    BgwrBgEEAdkvAQEBAQYwPQYJYIZIAYb4QgEEBDAWLmh0dHA6Ly9jYS5ncmlkLXN1\r\n
    cHBvcnQuYWMudmT4sopwqlBWsvcHViL2NybC9jYWNybC5jcmwwPQYJYIZIAYb4Qg\r\n
    EDBDAWLmh0dHA6Ly9jYS5ncmlkLXN1cHBvcnQuYWMudWsvcHViL2NybC9jYWNybC\r\n
    5jcmwwPwYDVR0fBDgwNjA0oDKgMIYuaHR0cDovL2NhLmdyaWQt5hYy51ay9wdWIv\r\n
    Y3JsL2NhY3JsLmNybDANBgkqhkiG9w0BAQUFAAOCAQEAS/U4iiooBENGW/Hwmmd3\r\n
    XCy6Zrt08YjKCzGNjorT98g8uGsqYjSxv/hmi0qlnlHs+k/3Iobc3LjS5AMYr5L8\r\n
    UO7OSkgFFlLHQyC9JzPfmLCAugvzEbyv4Olnsr8hbxF1MbKZoQxUZtMVu29wjfXk\r\n
    hTeApBv7eaKCWpSp7MCbvgzm74izKhu3vlDk9w6qVrxePfGgpKPqfHiOoGhFnbTK\r\n
    wTC6o2xq5y0qZ03JonF7OJspEd3I5zKY3E+ov7/ZhW6DqT8UFvsAdjvQbXyhV8Eu\r\n
    Yhixw1aKEPzNjNowuIseVogKOLXxWI5vAi5HgXdS0/ES5gDGsABo4fqovUKlgop3\r\n
    RA==\r\n
    -----END CERTIFICATE-----""".replace("\n\n", "\n")
    tests = t.request("016.http", {
        "method": "GET",
        "uri": t.uri("/"),
        "version": (1, 1),
        "headers": [("X-SSL-Cert", certificate)],
        "body": ""
    })
    for case in tests.gen_cases():
        yield case


for t in test_001():
    print "######", t[0], t[1]
    t[0](t[1], t[2], t[3])
