# Owners and file capabilities of the stock vendor that the default fs_config rules of the build do not give
# (taken from the stock vendor image: uid/gid and the security.capability xattr).

[vendor/bin/pm-service]
mode: 0755
user: AID_SYSTEM
group: AID_SYSTEM
caps: NET_BIND_SERVICE

[vendor/bin/loc_launcher]
mode: 0755
user: AID_GPS
group: AID_GPS
caps: SETGID SETUID

[vendor/bin/hw/android.hardware.bluetooth@1.0-service-qti]
mode: 0755
user: AID_SYSTEM
group: AID_SYSTEM
caps: NET_ADMIN BLOCK_SUSPEND
