# Tailscale

Tailscale is a Mesh VPN service based on the WireGuard protocol - https://www.tailscale.com.

Any devices logged into the same Tailnet are accessible form each other.

## Taildrop
For Linux machines any files received are pulled down as `root` into the Tailscale directory.

There are CLI commands to send/receive files - https://tailscale.com/kb/1106/taildrop?tab=linux

I have created a script created to simplify the usage of these commands (see `/scripts/taildrop.sh`)

[fegyizoli](https://github.com/fegyizoli) created a multiplatform python3 variant of it.

### Receiving files

#### bash

Files transferred to a Linux machine are by default owned by `root` and put in the Tailscale directory.  This script will transfer them from there to the `~/Downloads` directory.  Usage is as below.  If files are already in the Tailscale directory it will transfer them and exit.  If no files are in the Tailscale directory it will sit waiting for files to be transferred via the Tailnet and then move them across.

``` bash
~/scripts/tailnet.sh r
```

#### python3

You can set any directory you want with this variant.

``` bash
python3 ~/scripts/taildrop.py -r ~/wherever/you/want/to/receive
```

### Sending files

#### bash

Use the below command to send files to another device on the Tailnet.  It will show a list of currently active devices, just pick this to select the target device.

``` bash
~/scripts/tailnet.sh s example.txt
```

#### python3

Set a directory to send. You can highlight with a checkbox window which files you want to send from that directory. After that the target device can be selected. Only one of the idle or active devices can be selected.

``` bash
python3 ~/scripts/taildrop.py -s ~/files/to/send
```
