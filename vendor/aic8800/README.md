# Shared AIC8800 SDIO compatibility patches

Source: `https://github.com/radxa-pkg/aic8800`, pinned in `lib/aic8800.sh`
to `516e3b087763d80c44f5e3b6d2dd63e0d925c91d`.

These are the existing m28k patches, shared with A5E. `0001` contains only
the SDIO transport changes; the unused USB/PCIe hunks are intentionally
excluded (the USB hunks no longer apply to the pinned source). `0002`
adapts the cfg80211 callbacks to Linux 6.18. `0003` corrects the vendor's
`custregd=true` initializer to the documented `false` default so standard
cfg80211 regulatory selection applies. Optional board-local patches
are applied after these shared patches.

Build against the exact target kernel's prepared tree and sign with its
key. Strip debug sections **before** signing. Never disable enforced
module signatures or cfg80211 regulatory database verification to load
this driver. Bluetooth is not enabled by this Wi-Fi-only integration.

A5E selects the `aic8800D80` firmware directory rather than flattening
unrelated chip variants. Its paired firmware/kernel DT patches follow
Armbian build `0648ff3c4125d673c18b5f032dc7c28545c542b5`, backports
`22-Enable-wifi-on-Radxa-Cubie-A5E.patch` and
`34-fix-wifi-regulator-cubie-a5e.patch` (original attribution retained).
