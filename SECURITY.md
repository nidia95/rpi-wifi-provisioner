# Security Policy

## Threat model

WiFiPortal-RPi provisions a headless Raspberry Pi over a temporary,
unauthenticated-by-default Wi-Fi hotspot. Please understand the tradeoffs
before deploying it anywhere you don't fully control:

- **Anyone in radio range can see and join the hotspot** while it's active
  (protected only by the hotspot password set during install).
- **The provisioning protocol is a single UDP datagram.** By default,
  `install.sh` generates a random provisioning token that the server
  requires before it will act on a request — this stops a stranger who
  merely joined the hotspot from redirecting the Pi's network connection.
  It does **not** encrypt the payload: the target SSID and password are
  sent in cleartext on the local hotspot link. Treat the hotspot itself,
  not just the token, as the security boundary.
- **The provisioning window is short but real.** Once the Pi is
  provisioned it drops the hotspot, so exposure is limited to first-boot
  / re-provisioning windows — but during that window, anyone with the
  hotspot password and the token can act as a legitimate client.

**Recommended usage:** only run this on networks/devices you physically
control, change the generated hotspot password and token if you suspect
they leaked, and don't reuse a Pi's provisioning token across devices.

## Reporting a vulnerability

If you find a security issue, please open a private report via
[GitHub Security Advisories](../../security/advisories/new) rather than
a public issue. We'll aim to acknowledge reports within a few days.
