# RFC Documentation for Special IPv4 Address Ranges

This document describes the special IPv4 address ranges that LanCalc automatically detects and handles according to RFC specifications.

## Table of Contents

- [RFC 3330 - Loopback Addresses](#rfc-3330---loopback-addresses)
- [RFC 3927 - Link-Local Addresses](#rfc-3927---link-local-addresses)
- [RFC 5771 - Multicast Addresses](#rfc-5771---multicast-addresses)
- [RFC 1122 - Unspecified Addresses](#rfc-1122---unspecified-addresses)
- [RFC 919 - Broadcast Address](#rfc-919---broadcast-address)

---

## RFC 3330 - Loopback Addresses

### Official IETF Document

[RFC 3330 - Special-Use IPv4 Addresses](https://tools.ietf.org/html/rfc3330)

### Description

The loopback address range 127.0.0.0/8 is reserved for communication within the same host. These addresses are not routable on the Internet and are used for internal host-to-host communication, typically for testing and diagnostics.

### Example CLI Output

```bash
$ lancalc 127.0.0.1/8 --json
{
  "network": "127.0.0.0",
  "prefix": "/8",
  "netmask": "255.0.0.0",
  "broadcast": "*",
  "hostmin": "127.0.0.1",
  "hostmax": "127.255.255.254",
  "hosts": "16777214",
  "comment": "RFC 3330 Loopback (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-3330---loopback-addresses)"
}
```

### Notes

- Loopback addresses show actual host range calculations for subnet analysis
- The entire 127.0.0.0/8 range is reserved, not just 127.0.0.1
- Commonly used for localhost communication and application testing


---

## RFC 3927 - Link-Local Addresses

### Official IETF Document

[RFC 3927 - Dynamic Configuration of IPv4 Link-Local Addresses](https://tools.ietf.org/html/rfc3927)

### Description

The link-local address range 169.254.0.0/16 is used for automatic IP address configuration when no DHCP server is available. These addresses are not routable beyond the local network segment and are typically assigned automatically by the operating system.

### Example CLI Output

```bash
$ lancalc 169.254.1.1/16 --json
{
  "network": "169.254.0.0",
  "prefix": "/16",
  "netmask": "255.255.0.0",
  "broadcast": "*",
  "hostmin": "*",
  "hostmax": "*",
  "hosts": "*",
  "comment": "RFC 3927 Link-local (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-3927---link-local-addresses)"
}
```

### Notes

- Host-related fields show "*" because link-local addresses have special automatic assignment behavior
- Commonly seen on Windows systems when DHCP fails (APIPA - Automatic Private IP Addressing)
- Used for local communication only, not routable through gateways

---

## RFC 5771 - Multicast Addresses

### Official IETF Document

[RFC 5771 - IANA Guidelines for IPv4 Multicast Address Assignments](https://tools.ietf.org/html/rfc5771)

### Description

The multicast address range 224.0.0.0/4 (224.0.0.0 - 239.255.255.255) is reserved for IP multicast communication. These addresses are used to send data to multiple hosts simultaneously and are not intended for traditional unicast host addressing.

### Example CLI Output

```bash
$ lancalc 224.0.0.1/4 --json
{
  "network": "224.0.0.0",
  "prefix": "/4",
  "netmask": "240.0.0.0",
  "broadcast": "*",
  "hostmin": "*",
  "hostmax": "*",
  "hosts": "*",
  "comment": "RFC 5771 Multicast (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)"
}
```

### Notes

- Host-related fields show "*" because multicast addresses are not used for individual host identification
- Used for protocols like IGMP, streaming media, and group communication
- Different from broadcast as they require explicit group membership

---

## RFC 1122 - Unspecified Addresses

### Official IETF Document

[RFC 1122 - Requirements for Internet Hosts -- Communication Layers](https://tools.ietf.org/html/rfc1122)

### Description

The unspecified address range 0.0.0.0/8 contains addresses that have special meaning in network protocols. The address 0.0.0.0 is used to indicate "this host on this network" and should not be used for regular host addressing. Note that 0.0.0.0/0 (the default route) is treated as normal unicast.

### Example CLI Output

```bash
$ lancalc 0.0.0.1/8 --json
{
  "network": "0.0.0.0",
  "prefix": "/8",
  "netmask": "255.0.0.0",
  "broadcast": "*",
  "hostmin": "*",
  "hostmax": "*",
  "hosts": "*",
  "comment": "RFC 1122 Unspecified (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-1122---unspecified-addresses)"
}
```

### Notes

- Host-related fields show "*" because these addresses have special protocol meanings
- 0.0.0.0 is used in DHCP and routing protocols to indicate "this network"
- The default route 0.0.0.0/0 is treated as normal unicast, not unspecified

---

## RFC 919 - Broadcast Address

### Official IETF Document

[RFC 919 - Broadcasting Internet Datagrams](https://tools.ietf.org/html/rfc919)

### Description

The limited broadcast address 255.255.255.255 is used to send packets to all hosts on the local network segment. This address is never forwarded by routers and is used for network-wide announcements and discovery protocols.

### Example CLI Output

```bash
$ lancalc 255.255.255.255/32 --json
{
  "network": "255.255.255.255",
  "prefix": "/32",
  "netmask": "255.255.255.255",
  "broadcast": "*",
  "hostmin": "*",
  "hostmax": "*",
  "hosts": "*",
  "comment": "RFC 919 Broadcast (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-919---broadcast-address)"
}
```

### Notes

- Host-related fields show "*" because the broadcast address is not used for individual host addressing
- Different from directed broadcast (network broadcast address) as this is the limited broadcast
- Used by protocols like DHCP, ARP, and Wake-on-LAN
