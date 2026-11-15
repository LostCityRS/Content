#!/usr/bin/env python3
"""Buy an item from one shop, sell it to another, and come out ahead.

    python3 tools/shoparbitrage.py
    python3 tools/shoparbitrage.py --all

A REPORT, NOT A VERDICT, and not in the CI matrix - same reason as deaddata.py. Exits 0.

THE BUG IT LOOKS FOR is a money printer. Both shop prices scale the same number, oc_cost of the
item: what a player PAYS is cost scaled by the keeper's shop_sell_multiplier and what a player
RECEIVES is cost scaled by shop_buy_multiplier, both per-mille, both through ~calc_shop_value. The
item's own cost therefore cancels out of the comparison, and a profitable loop exists for an item
exactly when some shop's sell multiplier is below some other shop's buy multiplier - for the same
item, in the same currency. No prices need to be evaluated to find one.

The danger is concentrated in two places, and brewing.inv already names the shape of it in prose:
"a shop that buys anything and pays in ectotokens would turn a bronze dagger into Port Phasmatys
currency". The two places are allstock=yes, where a shop will buy an item it does not stock, and a
keeper whose multipliers are unusual.

WHAT THE SCALE MEANS, because the raw numbers mislead. ~calc_shop_value ends in
scale($int5, 1000, $base_cost), so 1000 is par and 550 is 55% of cost. The params' own declared
defaults are 100 and 60, which are on the OLD scale and would be 10% and 6% - no keeper uses them,
but a new keeper that sets neither would inherit them, which is worth knowing before adding one.
There is also a floor: $int5 = max(100, ...), so no multiplier is ever effectively below 100. A
keeper selling at 20 is really selling at 100, and this tool compares the floored values.

WHAT THE FIRST RUN FOUND - two real loops, both verified by hand afterwards, both still open
because closing them means choosing a price and that is not a decision to make from here.

  ruby_ring    Irksol's cheapringshop sells it at 500, half of its 2,025 cost, about 1,012gp.
               Grum's goldshop stocks ruby_ring and buys at 700, about 1,417gp. Both in coins,
               both restocking. That is roughly 405gp a ring for walking between two counters.
               Noterazzo pays 600 for it as well, so there are two ways round.
  ale_yeast    Blandebir SETS NO MULTIPLIERS AT ALL - his npc block carries owned_shop and
               shop_title and nothing else - so he inherits the declared defaults of 100 and 60,
               which are on the pre-migration scale and mean 10% and 6%. He sells 25gp yeast for
               2gp. Noterazzo's taxfree is allstock=yes and pays 600, so 15gp. Buy at two, sell at
               fifteen, on a shop that restocks ten at a time.

He is the only keeper of 199 who omits both, so this is one shop added without its prices rather
than a migration that missed. Two fixes present themselves and they are not equivalent: give
Blandebir explicit multipliers like every other keeper, or move the params' own defaults to 1000
and 600 so the next keeper added without them inherits par instead of a tenth of cost. The second
also fixes the one keeper that omits only shop_buy_multiplier.

brewing.inv's own comment worried about exactly this shape one shop over - "a shop that buys
anything and pays in ectotokens would turn a bronze dagger into Port Phasmatys currency" - and
Metarialus, the shop it was written about, is fine. Blandebir, named in the same comment two lines
up, is the one that is not.

WHAT IT DELIBERATELY DOES NOT MODEL. ~price_mod moves a price as stock drifts from its norm, scaled
by shop_delta, so buying out a shop raises its price and dumping stock on one lowers its payout.
That damping means a loop found here is finite rather than infinite - but the early trades still
pay, so a hit is a finding and not a curiosity. It also ignores stock quantity and restock rate for
the same reason.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')

SELL_DEFAULT = 100   # shop_sell_multiplier's declared default, on the old scale
BUY_DEFAULT = 60     # shop_buy_multiplier's declared default
FLOOR = 100          # $int5 = max(100, ...) in ~calc_shop_value


def walk(exts):
    for base, _dirs, files in os.walk(SCRIPTS):
        for f in files:
            if f.endswith(exts):
                yield os.path.join(base, f)


def read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        return fh.read()


def parse_blocks(path):
    """[name] -> {key: [values]} for one config file, comments stripped."""
    out, cur = {}, None
    for line in read(path).splitlines():
        line = line.split('//')[0].strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1]
            out[cur] = {}
        elif cur and '=' in line:
            k, v = line.split('=', 1)
            out[cur].setdefault(k.strip(), []).append(v.strip())
    return out


def shops():
    """Shop inventories: name -> {'allstock': bool, 'stock': set(obj), 'where': path}."""
    found = {}
    for path in walk(('.inv',)):
        rel = os.path.relpath(path, ROOT)
        for name, fields in parse_blocks(path).items():
            stock = set()
            for key, vals in fields.items():
                if re.fullmatch(r'stock\d+', key):
                    for v in vals:
                        obj = v.split(',')[0].strip()
                        if obj:
                            stock.add(obj)
            allstock = fields.get('allstock', ['no'])[0] == 'yes'
            shared = fields.get('scope', [''])[0] == 'shared'
            if stock or allstock:
                found[name] = {'allstock': allstock, 'stock': stock, 'where': rel, 'shared': shared}
    return found


def keepers():
    """Every npc that owns a shop, with the terms it offers."""
    out = []
    for path in walk(('.npc',)):
        rel = os.path.relpath(path, ROOT)
        for name, fields in parse_blocks(path).items():
            params = {}
            for v in fields.get('param', []):
                bits = v.split(',', 1)
                if len(bits) == 2:
                    params[bits[0].strip()] = bits[1].strip()
            if 'owned_shop' not in params:
                continue
            def num(key, dflt):
                try:
                    return int(params.get(key, dflt))
                except ValueError:
                    return dflt
            out.append({
                'npc': name,
                'shop': params['owned_shop'],
                'sell': max(FLOOR, num('shop_sell_multiplier', SELL_DEFAULT)),
                'buy': max(FLOOR, num('shop_buy_multiplier', BUY_DEFAULT)),
                'currency': params.get('shop_currency', 'coins'),
                'where': rel,
            })
    return out


def main():
    show_all = '--all' in sys.argv
    inv = shops()
    ks = keepers()

    print('%d shop inventories, %d keepers that own one' % (len(inv), len(ks)))
    orphan_shops = sorted(n for n in inv if not any(k['shop'] == n for k in ks))
    if orphan_shops:
        print('%d shop inventories no keeper owns (nothing opens them): %s'
              % (len(orphan_shops), ', '.join(orphan_shops[:6]) + ('...' if len(orphan_shops) > 6 else '')))
    print('')

    # Best terms available to a player, per (item, currency): cheapest purchase, richest payout.
    cheapest = {}   # (item, currency) -> (mult, npc)
    richest = {}    # (item, currency) -> (mult, npc)
    anybuyers = {}  # currency -> list of (mult, npc) for allstock=yes shops

    for k in ks:
        shop = inv.get(k['shop'])
        if not shop:
            continue
        cur = k['currency']
        for item in shop['stock']:
            key = (item, cur)
            if key not in cheapest or k['sell'] < cheapest[key][0]:
                cheapest[key] = (k['sell'], k['npc'])
            if key not in richest or k['buy'] > richest[key][0]:
                richest[key] = (k['buy'], k['npc'])
        if shop['allstock']:
            anybuyers.setdefault(cur, []).append((k['buy'], k['npc']))

    hits = []
    for (item, cur), (sell, seller) in sorted(cheapest.items()):
        best_buy, buyer = richest.get((item, cur), (0, None))
        for mult, npc in anybuyers.get(cur, []):
            if mult > best_buy:
                best_buy, buyer = mult, npc
        if buyer and best_buy > sell:
            hits.append((item, cur, sell, seller, best_buy, buyer))

    if hits:
        print('-- %d item/currency pairs where buying low and selling high pays' % len(hits))
        for item, cur, sell, seller, buy, buyer in hits:
            print('   %-28s in %-14s buy at %4d from %-22s sell at %4d to %s  (+%d per mille)'
                  % (item, cur, sell, seller, buy, buyer, buy - sell))
    else:
        print('-- no item can be bought from one shop and sold to another at a profit')
        print('   checked %d item/currency pairs across %d currencies'
              % (len(cheapest), len({c for _, c in cheapest})))
        worst = sorted(
            ((sell - richest.get((i, c), (0, None))[0], i, c, sell) for (i, c), (sell, _) in cheapest.items()),
        )[:5]
        print('   the narrowest margins, closest first (a negative gap would be a hit):')
        for gap, item, cur, sell in worst:
            best = richest.get((item, cur), (0, None))[0]
            print('     %-28s in %-12s costs %4d, best payout %4d, gap %d' % (item, cur, sell, best, gap))

    if show_all:
        print('')
        print('-- every keeper, cheapest purchase multiplier first')
        for k in sorted(ks, key=lambda k: k['sell']):
            print('   %-30s %-22s sell %4d buy %4d in %s'
                  % (k['npc'], k['shop'], k['sell'], k['buy'], k['currency']))

    print('')
    print('a report, not a verdict: nothing here is asserted and the exit code is always 0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
