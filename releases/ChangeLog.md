# Change Log

This lists the changes in the most recent firmware, for each hardware platform.

# Shared Improvements - Both Mk4 and Q

- New signing features:
    - Sign message from note text, or password note
    - JSON message signing. Use JSON object to pass data to sign in form
        `{"msg":"<required msg>","subpath":"<optional sp>","addr_fmt": "<optional af>"}`
    - Sign message with key resulting from positive ownership check. Press (0) and
      enter or scan message text to be signed.
    - Sign message with key selected from Address Explorer Custom Path menu. Press (2) and
      enter or scan message text to be signed.
- Enhancement: New address display format improves address verification on screen (groups of 4).
- Deltamode enhancements:
    - Hide Secure Notes & Passwords in Deltamode. Wipe seed if notes menu accessed. 
    - Hide Seed Vault in Deltamode. Wipe seed if Seed Vault menu accessed. 
    - Catch more DeltaMode cases in XOR submenus. Thanks [@dmonakhov](https://github.com/dmonakhov)
- Enhancement: Add ability to switch between BIP-32 xpub, and obsolete SLIP-132 format
  in `Export XPUB`
- Enhancement: Use the fact that master seed cannot be used as ephemeral seed, to show message 
  about successful master seed verification.
- Enhancement: Allow devs to override backup password.
- Enhancement: Add option to show/export full multisg addresses without censorship. Enable
  in `Settings > Multisig Wallets > Full Address View`.
- Enhancement: If derivation path is omitted during message signing, derivation path
  default is no longer root (m), instead it is based on requested address format
  (`m/44h/0h/0h/0/0` for p2pkh, and `m/84h/0h/0h/0/0` for p2wpkh). Conversely,
  if address format is not provided but subpath derivation starts with:
  `m/84h/...` or `m/49h/...`, then p2wpkh or p2sh-p2wpkh respectively, is used.
- Bugfix: Sometimes see a struck screen after _Verifying..._ in boot up sequence.
  On Q, result is blank screen, on Mk4, result is three-dots screen.
- Bugfix: Do not allow to enable/disable Seed Vault feature when in temporary seed mode.
- Bugfix: Bless Firmware causes hanging progress bar.
- Bugfix: Prevent yikes in ownership search.
- Bugfix: Factory-disabled NFC was not recognized correctly.
- Bugfix: Be more robust about flash filesystem holding the settings.
- Bugfix: Do not include sighash in PSBT input data, if sighash value is `SIGHASH_ALL`.
- Bugfix: Allow import of multisig descriptor with root (m) keys in it.
  Thanks [@turkycat](https://github.com/turkycat)
- Change: Do not purge settings of current active tmp seed when deleting it from Seed Vault.
- Change: Rename Testnet3 -> Testnet4 (all parameters unchanged).


# Mk4 Specific Changes

## 5.4.1 - 2025-02-13

- Enhancement: Export single sig descriptor with simple QR.


# Q Specific Changes

## 1.3.1Q - 2025-02-13

- New Feature: Verify Signed RFC messages via BBQr
- New Feature: Sign message from QR scan (format has to be JSON)
- Enhancement: Sign/Verify Address in Sparrow via QR
- Enhancement: Sign scanned Simple Text by pressing (0). Next screen query information
  about which key to use.
- Enhancement: Add option to "Sort By Title" in Secure Notes and Passwords. Thanks to
  [@MTRitchey](https://x.com/MTRitchey) for suggestion.
- Bugfix: Properly re-draw status bar after Restore Master on COLDCARD without master seed.



# Release History

- [`History-Q.md`](History-Q.md)
- [`History-Mk4.md`](History-Mk4.md)
- [`History-Mk3.md`](History-Mk3.md)

