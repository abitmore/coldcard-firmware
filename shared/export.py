# (c) Copyright 2018 by Coinkite Inc. This file is covered by license found in COPYING-CC.
#
# export.py - Export and share various semi-public data
#
import stash, chains, version, ujson, ngu
from uio import StringIO
from ucollections import OrderedDict
from utils import xfp2str, swab32
from ux import ux_show_story, import_export_prompt
from glob import settings
from msgsign import write_sig_file
from public_constants import AF_CLASSIC, AF_P2WPKH, AF_P2WPKH_P2SH, AF_P2WSH, AF_P2WSH_P2SH, AF_P2SH
from charcodes import KEY_NFC, KEY_CANCEL, KEY_QR
from ownership import OWNERSHIP

async def export_by_qr(body, label, type_code, force_bbqr=False):
    # render as QR and show on-screen
    from ux import show_qr_code

    try:
        if force_bbqr or len(body) > 2000:
            raise ValueError

        await show_qr_code(body)
    except (ValueError, RuntimeError, TypeError):
        if version.has_qwerty:
            # do BBQr on Q
            from ux_q1 import show_bbqr_codes
            await show_bbqr_codes(type_code, body, label)

        # on Mk4, if too big ... just do nothing (but JSON should have fit?)

    return


async def export_contents(title, contents, fname_pattern, derive=None, addr_fmt=None,
                          is_json=False, force_bbqr=False, force_prompt=False):
    # export text and json files while offering NFC, QR & Vdisk
    # produces signed export in case of SD/Vdisk (signed with key at deriv and addr_fmt)
    # checks if suitable to offer QR export on Mk4
    # argument contents can support function that generates content
    from glob import dis, NFC, VD
    from files import CardSlot, CardMissingError, needs_microsd
    from qrs import MAX_V11_CHAR_LIMIT

    if callable(contents):
        dis.fullscreen('Generating...')
        contents, derive, addr_fmt = contents()

    # figure out if offering QR code export make sense given HW
    # len() is O(1)
    no_qr = not version.has_qwerty and (len(contents) >= MAX_V11_CHAR_LIMIT)

    sig = not (derive is None and addr_fmt is None)

    while True:
        ch = await import_export_prompt("%s file" % title,
                                        force_prompt=force_prompt, no_qr=no_qr)
        if ch == KEY_CANCEL:
            break
        elif ch == KEY_QR:
            await export_by_qr(contents, title, "J" if is_json else "U", force_bbqr=force_bbqr)
            continue
        elif ch == KEY_NFC:
            if is_json:
                await NFC.share_json(contents)
            else:
                await NFC.share_text(contents)
            continue

        # choose a filename
        try:
            dis.fullscreen("Saving...")
            with CardSlot(**ch) as card:
                fname, nice = card.pick_filename(fname_pattern)

                # do actual write
                with open(fname, 'wt' if is_json else 'wb') as fd:
                    fd.write(contents)

                if sig:
                    h = ngu.hash.sha256s(contents.encode())
                    sig_nice = write_sig_file([(h, fname)], derive, addr_fmt)

            msg = '%s file written:\n\n%s' % (title, nice)
            if sig:
                msg += "\n\n%s signature file written:\n\n%s" % (title, sig_nice)

            await ux_show_story(msg)

        except CardMissingError:
            await needs_microsd()
        except Exception as e:
            await ux_show_story('Failed to write!\n\n\n' + str(e))

        # both exceptions & success gets here
        if no_qr and (NFC is None) and (VD is None) and not force_prompt:
            # user has no other ways enabled, we already exported to SD - done
            return

def generate_public_contents():
    # Generate public details about wallet.
    #
    # simple text format: 
    #   key = value
    # or #comments
    # but value is JSON

    num_rx = 5

    chain = chains.current_chain()

    with stash.SensitiveValues() as sv:

        xfp = xfp2str(swab32(sv.node.my_fp()))

        yield ('''\
# Coldcard Wallet Summary File
## For wallet with master key fingerprint: {xfp}

Wallet operates on blockchain: {nb}

For BIP-44, this is coin_type '{ct}', and internally we use
symbol {sym} for this blockchain.

## IMPORTANT WARNING

**NEVER** deposit to any address in this file unless you have a working
wallet system that is ready to handle the funds at that address!

## Top-level, 'master' extended public key ('m/'):

{xpub}

What follows are derived public keys and payment addresses, as may
be needed for different systems.


'''.format(nb=chain.name, xpub=chain.serialize_public(sv.node), 
            sym=chain.ctype, ct=chain.b44_cointype, xfp=xfp))

        for name, path, addr_fmt in chains.CommonDerivations:
            path = path.replace('{coin_type}', str(chain.b44_cointype))

            yield ('''## For {name}: {path}\n\n'''.format(name=name, path=path))
            yield ('''First %d receive addresses (account=0, change=0):\n\n''' % num_rx)

            submaster = None
            for i in range(num_rx):
                subpath = path.format(account=0, change=0, idx=i)

                # find the prefix of the path that is hardneded
                if "h" in subpath:
                    hard_sub = subpath.rsplit("h", 1)[0] + "h"
                else:
                    hard_sub = 'm'

                if hard_sub != submaster:
                    # dump the xpub needed

                    if submaster:
                        yield "\n"

                    node = sv.derive_path(hard_sub, register=False)
                    yield ("%s => %s\n" % (hard_sub, chain.serialize_public(node)))
                    if addr_fmt != AF_CLASSIC and (addr_fmt in chain.slip132):
                        yield ("%s => %s   ##SLIP-132##\n" % (
                                    hard_sub, chain.serialize_public(node, addr_fmt)))

                    submaster = hard_sub
                    node.blank()
                    del node

                # show the payment address
                node = sv.derive_path(subpath, register=False)
                yield ('%s => %s\n' % (subpath, chain.address(node, addr_fmt)))

                node.blank()
                del node

            yield ('\n\n')

    from multisig import MultisigWallet
    if MultisigWallet.exists():
        yield '\n# Your Multisig Wallets\n\n'

        for ms in MultisigWallet.get_all():
            fp = StringIO()

            ms.render_export(fp)
            print("\n---\n", file=fp)

            yield fp.getvalue()
            del fp


async def make_summary_file(fname_pattern='public.txt'):
    from glob import dis

    # record **public** values and helpful data into a text file
    dis.fullscreen('Generating...')

    # generator function:
    body = "".join(list(generate_public_contents()))
    ch = chains.current_chain()
    await export_contents('Summary', body, fname_pattern,
                          "m/44h/%dh/0h/0/0" % ch.b44_cointype,
                          AF_CLASSIC)

async def make_bitcoin_core_wallet(account_num=0, fname_pattern='bitcoin-core.txt'):
    from glob import dis
    xfp = xfp2str(settings.get('xfp'))

    dis.fullscreen('Generating...')

    # make the data
    examples = []
    imp_multi, imp_desc = generate_bitcoin_core_wallet(account_num, examples)

    imp_multi = ujson.dumps(imp_multi)
    imp_desc = ujson.dumps(imp_desc)

    body = '''\
# Bitcoin Core Wallet Import File

https://github.com/Coldcard/firmware/blob/master/docs/bitcoin-core-usage.md

## For wallet with master key fingerprint: {xfp}

Wallet operates on blockchain: {nb}

## Bitcoin Core RPC

The following command can be entered after opening Window -> Console
in Bitcoin Core, or using bitcoin-cli:

importdescriptors '{imp_desc}'

> **NOTE** If your UTXO was created before generating `importdescriptors` command, you should adjust the value of `timestamp` before executing command in bitcoin core. 
  By default it is set to `now` meaning do not rescan the blockchain. If approximate time of UTXO creation is known - adjust `timestamp` from `now` to UNIX epoch time.
  0 can be specified to scan the entire blockchain. Alternatively `rescanblockchain` command can be used after executing importdescriptors command.

### Bitcoin Core before v0.21.0 

This command can be used on older versions, but it is not as robust
and "importdescriptors" should be prefered if possible:

importmulti '{imp_multi}'

## Resulting Addresses (first 3)

'''.format(imp_multi=imp_multi, imp_desc=imp_desc, xfp=xfp, nb=chains.current_chain().name)

    body += '\n'.join('%s => %s' % t for t in examples)

    body += '\n'

    OWNERSHIP.note_wallet_used(AF_P2WPKH, account_num)

    ch = chains.current_chain()
    derive = "84h/{coin_type}h/{account}h".format(account=account_num, coin_type=ch.b44_cointype)
    await export_contents('Bitcoin Core', body, fname_pattern, derive + "/0/0", AF_P2WPKH)

def generate_bitcoin_core_wallet(account_num, example_addrs):
    # Generate the data for an RPC command to import keys into Bitcoin Core
    # - yields dicts for json purposes
    from descriptor import Descriptor

    chain = chains.current_chain()

    derive = "84h/{coin_type}h/{account}h".format(account=account_num,
                                                  coin_type=chain.b44_cointype)

    with stash.SensitiveValues() as sv:
        prefix = sv.derive_path(derive)
        xpub = chain.serialize_public(prefix)

        for i in range(3):
            sp = '0/%d' % i
            node = sv.derive_path(sp, master=prefix)
            a = chain.address(node, AF_P2WPKH)
            example_addrs.append( ('m/%s/%s' % (derive, sp), a) )

    xfp = settings.get('xfp')
    _, vers, _ = version.get_mpy_version()

    OWNERSHIP.note_wallet_used(AF_P2WPKH, account_num)

    desc_obj = Descriptor(keys=[(xfp, derive, xpub)], addr_fmt=AF_P2WPKH)
    # for importmulti
    imm_list = [
        {
            'desc': desc_obj.serialize(internal=internal),
            'range': [0, 1000],
            'timestamp': 'now',
            'internal': internal,
            'keypool': True,
            'watchonly': True
        }
        for internal in [False, True]
    ]
    # for importdescriptors
    imd_list = desc_obj.bitcoin_core_serialize()
    return imm_list, imd_list

def generate_wasabi_wallet():
    # Generate the data for a JSON file which Wasabi can open directly as a new wallet.
    import version

    # bitcoin (xpub) is used, even for testnet case (i.e. no tpub)
    # even though wasabi can properly parse tpub and generate correct addresses
    # it would be confusing for user if he sees tpub in our export and then xpub in wasabi
    # therefore we rather export xpub with correct testnet derivation path
    btc = chains.BitcoinMain

    with stash.SensitiveValues() as sv:
        dd = "84h/%dh/0h" % chains.current_chain().b44_cointype
        xpub = btc.serialize_public(sv.derive_path(dd))

    xfp = settings.get('xfp')
    txt_xfp = xfp2str(xfp)

    # chain = chains.current_chain()
    # https://docs.wasabiwallet.io/using-wasabi/Testnet.html#activating-testnet-in-wasabi
    # https://github.com/zkSNACKs/WalletWasabi/blob/master/WalletWasabi.Documentation/WasabiSetupRegtest.md
    # as we do not shitcoin here - check is useless
    # would yikes on XRT
    # assert chain.ctype in {'BTC', 'XTN', 'XRT'}, "Only Bitcoin supported"

    _,vers,_ = version.get_mpy_version()

    rv = OrderedDict(ColdCardFirmwareVersion=vers, MasterFingerprint=txt_xfp, ExtPubKey=xpub)
    return ujson.dumps(rv), dd + "/0/0", AF_P2WPKH

def generate_unchained_export(account_num=0):
    # They used to rely on our airgapped export file, so this is same style
    # - for multisig purposes
    # - BIP-45 style paths for now
    # - no account numbers (at this level)

    chain = chains.current_chain()
    xfp = xfp2str(settings.get('xfp', 0))
    rv = OrderedDict(xfp=xfp, account=account_num)
    sign_der = None
    with stash.SensitiveValues() as sv:
        for name, deriv, fmt in chains.MS_STD_DERIVATIONS:
            if fmt == AF_P2SH and account_num:
                continue
            dd = deriv.format(coin=chain.b44_cointype, acct_num=account_num)
            if fmt == AF_P2WSH:
                sign_der = dd + "/0/0"
            node = sv.derive_path(dd)
            xp = chain.serialize_public(node, fmt)

            OWNERSHIP.note_wallet_used(fmt, account_num)

            rv['%s_deriv' % name] = dd
            rv[name] = xp

    return ujson.dumps(rv), sign_der, AF_CLASSIC

def generate_generic_export(account_num=0):
    # Generate data that other programers will use to import Coldcard (single-signer)
    from descriptor import Descriptor, multisig_descriptor_template

    chain = chains.current_chain()
    master_xfp = settings.get("xfp")
    master_xfp_str = xfp2str(master_xfp)

    rv = OrderedDict(chain=chain.ctype,
                     xfp=master_xfp_str,
                     account=account_num,
                     xpub=settings.get('xpub'))

    with stash.SensitiveValues() as sv:
        # each of these paths would have /{change}/{idx} in usage (not hardened)
        for name, deriv, fmt, atype, is_ms in [
            ( 'bip44', "m/44h/{ct}h/{acc}h", AF_CLASSIC, 'p2pkh', False ),
            ( 'bip49', "m/49h/{ct}h/{acc}h", AF_P2WPKH_P2SH, 'p2sh-p2wpkh', False ),   # was "p2wpkh-p2sh"
            ( 'bip84', "m/84h/{ct}h/{acc}h", AF_P2WPKH, 'p2wpkh', False ),
            ( 'bip48_1', "m/48h/{ct}h/{acc}h/1h", AF_P2WSH_P2SH, 'p2sh-p2wsh', True ),
            ( 'bip48_2', "m/48h/{ct}h/{acc}h/2h", AF_P2WSH, 'p2wsh', True ),
            ( 'bip45', "m/45h", AF_P2SH, 'p2sh', True ),
        ]:
            if fmt == AF_P2SH and account_num:
                continue

            dd = deriv.format(ct=chain.b44_cointype, acc=account_num)
            node = sv.derive_path(dd)
            xfp = xfp2str(swab32(node.my_fp()))
            xp = chain.serialize_public(node, AF_CLASSIC)
            zp = chain.serialize_public(node, fmt) if fmt != AF_CLASSIC else None
            if is_ms:
                desc = multisig_descriptor_template(xp, dd, master_xfp_str, fmt)
            else:
                desc = Descriptor(keys=[(master_xfp, dd, xp)], addr_fmt=fmt).serialize(int_ext=True)

                OWNERSHIP.note_wallet_used(fmt, account_num)

            rv[name] = OrderedDict(name=atype,
                                   xfp=xfp,
                                   deriv=dd,
                                   xpub=xp,
                                   desc=desc)

            if zp and zp != xp:
                rv[name]['_pub'] = zp

            if not is_ms:
                # bonus/check: first non-change address: 0/0
                node.derive(0, False).derive(0, False)
                rv[name]['first'] = chain.address(node, fmt)

    sig_deriv = "m/44h/{ct}h/{acc}h".format(ct=chain.b44_cointype, acc=account_num) + "/0/0"
    return ujson.dumps(rv), sig_deriv, AF_CLASSIC

def generate_electrum_wallet(addr_type, account_num):
    # Generate line-by-line JSON details about wallet.
    #
    # Much reverse enginerring of Electrum here. It's a complex
    # legacy file format.

    chain = chains.current_chain()

    xfp = settings.get('xfp')

    # Must get the derivation path, and the SLIP32 version bytes right!
    mode = chains.af_to_bip44_purpose(addr_type)

    OWNERSHIP.note_wallet_used(addr_type, account_num)

    derive = "m/{mode}h/{coin_type}h/{account}h".format(mode=mode,
                                    account=account_num, coin_type=chain.b44_cointype)

    with stash.SensitiveValues() as sv:
        top = chain.serialize_public(sv.derive_path(derive), addr_type)

    # most values are nicely defaulted, and for max forward compat, don't want to set
    # anything more than I need to

    rv = OrderedDict(seed_version=17, use_encryption=False, wallet_type='standard')

    lab = 'Coldcard Import %s' % xfp2str(xfp)
    if account_num:
        lab += ' Acct#%d' % account_num

    # the important stuff.
    rv['keystore'] = OrderedDict(type='hardware',
                                 hw_type='coldcard',
                                 label=lab,
                                 ckcc_xfp=xfp,
                                 ckcc_xpub=settings.get('xpub'),
                                 derivation=derive,
                                 xpub=top)

    return ujson.dumps(rv), derive + "/0/0", addr_type


async def make_descriptor_wallet_export(addr_type, account_num=0, mode=None, int_ext=True,
                                        fname_pattern="descriptor.txt"):
    from descriptor import Descriptor
    from glob import dis

    dis.fullscreen('Generating...')
    chain = chains.current_chain()

    xfp = settings.get('xfp')
    dis.progress_bar_show(0.1)
    if mode is None:
        mode = chains.af_to_bip44_purpose(addr_type)

    OWNERSHIP.note_wallet_used(addr_type, account_num)

    derive = "m/{mode}h/{coin_type}h/{account}h".format(mode=mode,
                                    account=account_num, coin_type=chain.b44_cointype)
    dis.progress_bar_show(0.2)
    with stash.SensitiveValues() as sv:
        dis.progress_bar_show(0.3)
        xpub = chain.serialize_public(sv.derive_path(derive))

    dis.progress_bar_show(0.7)
    desc = Descriptor(keys=[(xfp, derive, xpub)], addr_fmt=addr_type)
    dis.progress_bar_show(0.8)
    if int_ext:
        #  with <0;1> notation
        body = desc.serialize(int_ext=True)
    else:
        # external descriptor
        # internal descriptor
        body = "%s\n%s" % (
            desc.serialize(internal=False),
            desc.serialize(internal=True),
        )

    dis.progress_bar_show(1)
    await export_contents("Descriptor", body, fname_pattern, derive + "/0/0",
                          addr_type, force_prompt=True)

# EOF

