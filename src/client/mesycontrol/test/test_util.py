from nose.tools import assert_raises, assert_dict_equal
from ..util import parse_connection_url
from ..util import URLParseError

def test_parse_connection_url():
    d = parse_connection_url('serial:///dev/ttyUSB0@115200')
    assert_dict_equal(d, dict(serial_port='/dev/ttyUSB0', baud_rate=115200))

    d = parse_connection_url('serial:///dev/ttyUSB0')
    assert_dict_equal(d, dict(serial_port='/dev/ttyUSB0', baud_rate=9600))

    d = parse_connection_url('/dev/ttyUSB0@115200')
    assert_dict_equal(d, dict(serial_port='/dev/ttyUSB0', baud_rate=115200))

    for url in ('serial:///dev/ttyUSB0@', '/dev/ttyUSB0@', 'serial:///dev/ttyUSB0@foo',
            '/dev/ttyUSB0@foo', 'serial://@', '@9600', 'serial://@9600', '@', 'serial://'):
        assert_raises(URLParseError, parse_connection_url, url)

    d = parse_connection_url('tcp://example.com:666')
    assert_dict_equal(d, dict(host='example.com', port=666))

    d = parse_connection_url('tcp://example.com')
    assert_dict_equal(d, dict(host='example.com', port=4001))

    d = parse_connection_url('example.com:666')
    assert_dict_equal(d, dict(host='example.com', port=666))

    for url in ('tcp://example.com:', 'example.com:', 'tcp://example.com:foo',
            'example.com:foo', 'tcp://:', ':666', 'tcp://:666', ':', 'tcp://'):
        assert_raises(URLParseError, parse_connection_url, url)

    d = parse_connection_url('mesycontrol://example.com:666')
    assert_dict_equal(d, dict(mesycontrol_host='example.com', mesycontrol_port=666))

    d = parse_connection_url('mesycontrol://example.com')
    assert_dict_equal(d, dict(mesycontrol_host='example.com', mesycontrol_port=23000))

    for url in ('mesycontrol://example.com:', 'mesycontrol://example.com:foo',
            'mesycontrol://:', 'mesycontrol://:666',
            'mesycontrol://'):
        assert_raises(URLParseError, parse_connection_url, url)

    for url in ('://', 'fooproto://foo:bar'):
        assert_raises(URLParseError, parse_connection_url, url)
