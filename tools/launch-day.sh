#!/bin/sh
# Launch day, in order - and where the box says you are in it.
#
#   ./launch-day.sh              the sequence, with what this box reports about each step
#   ./launch-day.sh --quick      ...without the wipe's dry run, which is the slow part
#
# IT CHANGES NOTHING. Every command it runs itself is a read: a git branch, a count of rows, a
# listing of a backup directory, and the wipe's OWN DRY RUN, which prints what it would do and then
# says "Nothing was changed." The steps that act are printed for you to run, never run from here. A
# launch has one irreversible step in the middle of it, and a script that offers to do the whole
# thing unattended is a script that will one day wipe a world nobody meant to wipe.
#
# WHY THE ORDER IS THIS ORDER, which is the part worth reading once before the day:
#
#   the backup goes first        Everything after it is recoverable except the wipe.
#                                backup-offsite.sh takes the four things nothing else protects -
#                                the trading post, the clans, the vote ledger, and login-rsa.pem,
#                                whose modulus is baked into every released client - and puts them
#                                on another machine. The wipe takes its own backups, onto the disk
#                                it is protecting.
#
#   the deploy goes before       The wipe reads every character's save to count the vote points it
#   the wipe                     carries over, and reading a save needs data/pack. It also needs
#                                the schema the deploy migrates to: it checks its tables first and
#                                refuses on an old one, rather than reporting "0 rows" for a table
#                                that is not there. So the code and the packs have to be the launch
#                                ones before anything is cleared.
#
#   the world comes down         The wipe refuses while anybody is logged in, and it is right to:
#   between them                 the server holds a character in memory and writes the file at
#                                logout, so a save taken away underneath a live player comes
#                                straight back at the next logout. deploy.sh ENDS by restarting the
#                                world, so the stop is a step after it, not before.
#
#   the website goes last        A successful web deploy publishes the news post and announces it to
#                                Discord in the same run. The post says the trading post feeds
#                                Discord and that the boards start empty, and both are claims about
#                                an engine that has to be deployed and restarted first. Publish
#                                before that and the notes are briefly wrong.
#
#   the veteran grant has        It writes one column, read at login, and nothing in it reads a live
#   no place in the order        character - so it is safe with the world up, and correct before the
#                                wipe, straight after it, or in a week. It qualifies people by their
#                                save file, and the wipe MOVES saves to wiped-<stamp>/ rather than
#                                deleting them, so the wipe itself produces the roster it reads. It
#                                only ever grants.
#
# WHAT IS NOT HERE: anything the CI already answers. Both repos build, pack, lint and sim on every
# push, and the build runs CacheCheck at the end of every run - that is the corrupt-pack fault which
# shows up as a client stuck at 30% on "Connection error". If GitHub is green on 377-wip, the code
# is not the thing to worry about on the day.
set -u

QUICK=0
for a in "$@"; do
    case "$a" in
        --quick) QUICK=1 ;;
        *) echo "launch-day: unknown option $a" >&2; exit 2 ;;
    esac
done

# /opt/deathplateau and deathplateau.service since the server was named (2026-09-23); a box not yet
# moved over still has /opt/lostcity and lostcity.service. Same two fallbacks deploy.sh uses.
ROOT=${DP_ROOT:-/opt/deathplateau}
[ -d "$ROOT" ] || ROOT=/opt/lostcity
CONTENT=$ROOT/content
ENGINE=$ROOT/engine
WEB=$ROOT/web
PROFILE=${NODE_PROFILE:-main}
SERVICE=deathplateau.service
systemctl cat "$SERVICE" >/dev/null 2>&1 || SERVICE=lostcity.service

step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
cmd()  { printf '    \033[36m%s\033[0m\n' "$*"; }
note() { printf '      %s\n' "$*"; }

printf '\033[1mDeath Plateau - launch day\033[0m   (%s, profile %s, %s)\n' "$ROOT" "$PROFILE" "$SERVICE"
printf 'Nothing here acts. The commands are printed for you to run.\n'

# ---------------------------------------------------------------- before the day

step "0. Before the day. None of this is launch-day work, and all of it wants doing early"

cmd "cd $ENGINE && sh tools/server/rehearse-wipe.sh"
note "The real wipe against a consistent copy of the live data, with the world still up."
note "The only thing that proves the wipe against YOUR data rather than against a fixture."

cmd "cd $ROOT && ./deploy.sh --dev"
note "Builds the launch branch into World 2 - staff only, its own saves and database."
note "Play a fresh character there before doing it on the world people are watching."

cmd "cd $ENGINE && npx tsx tools/server/veteran.ts --list"
note "A read. Names the roster the grant would give the rank to, while there is still time"
note "to disagree with it."

# WHICH BRANCH EACH CHECKOUT IS ON, and not as a courtesy. On 11 November the live engine was
# checked out on a branch called dev-logging - the JAVA CLIENT is on dev-logging, the engine
# never was - while a local 377-wip sat beside it 613 commits behind. Live deploys did not care,
# because the pull is "git pull origin 377-wip" into whatever is checked out. But --dev clones
# --branch 377-wip from here, so a rebuilt dev world would have come up on the stale branch
# without complaining, and anybody reading git status was told the engine was somewhere it was
# not. It had printed the branch name here for two days and said nothing was wrong with it.
for what in content engine web; do
    case $what in
        content) dir=$CONTENT; want=377-wip ;;
        engine)  dir=$ENGINE;  want=377-wip ;;
        web)     dir=$WEB;     want=main ;;
    esac
    if [ ! -d "$dir/.git" ]; then
        note "$what: no checkout at $dir"
        continue
    fi
    branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
    tip=$(git -C "$dir" log --oneline -1 2>/dev/null)
    # --no-optional-locks, AND IT IS NOT OPTIONAL HERE. `git status` is a read in intent and a
    # WRITE in fact: it refreshes the index's cached stat data and saves it back. Run as root on a
    # checkout the game serves from, that leaves .git/index owned by root, and the next deploy as
    # lostcity dies with "index file open failed: Permission denied" - which is what happened on
    # 11 November, twice, the second time to this line. The flag is what git added for exactly
    # this: ask about the working tree and take no locks, write nothing.
    #
    # The other reads here - rev-parse, log, rev-list, show-ref - do not touch the index. This was
    # the only one, and the header's claim that every command is a read is true of them.
    dirty=$(git --no-optional-locks -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d " ")
    note "$what: $branch, $dirty local change(s), at $tip"
    if [ "$branch" != "$want" ]; then
        note "   NOT ON $want. Deploys still work - the pull goes into whatever is checked out -"
        note "   but --dev clones --branch $want from here, and this misleads anybody reading it."
        if git -C "$dir" show-ref --verify --quiet "refs/heads/$want"; then
            note "   AND there is a local $want that is NOT the one being deployed:"
            note "   $(git -C "$dir" log --oneline -1 "$want" 2>/dev/null)"
            note "   that is the branch --dev would clone. Sort this out before touching dev."
        fi
    fi
    # As of the last fetch: nothing here fetches, because nothing here touches the network.
    behind=$(git -C "$dir" rev-list --count "HEAD..origin/$want" 2>/dev/null || echo 0)
    if [ "${behind:-0}" -gt 0 ]; then
        note "   $behind commit(s) behind origin/$want as of the last fetch"
    fi
done
note "green on 377-wip? github.com/coreysho/DeathPlateau-Content/actions"
note "                  github.com/coreysho/DeathPlateau-Engine/actions"

# ---------------------------------------------------------------- the day itself

step "1. Everything that cannot be rebuilt, off the box"
cmd "cd $ENGINE && sh tools/server/backup-offsite.sh"
for d in /var/backups/dp-offsite /var/backups/dp-players; do
    if [ -d "$d" ]; then
        newest=$(ls -1t "$d" 2>/dev/null | head -1)
        note "$d: ${newest:-empty}"
    else
        note "$d: not there yet"
    fi
done

step "2. The launch build, with players warned first"
cmd "cd $ROOT && ./deploy.sh --countdown=300"
note "Pulls 377-wip in BOTH repos, builds, migrates the database, restarts the world. The"
note "build runs while the world is still up on the old code and the timer starts only once"
note "it has succeeded, so a build that fails leaves people playing, unwarned and unharmed."

step "3. The world down, because the wipe will not run otherwise"
cmd "systemctl stop $SERVICE"
if command -v systemctl > /dev/null 2>&1; then
    if systemctl is-active --quiet "$SERVICE"; then note "now: UP"; else note "now: down"; fi
fi

# IS THERE A SECOND PROCESS? With LOGIN_SERVER=true and EASY_STARTUP unset, app.ts does NOT
# spawn the login worker in-process - the engine talks over a socket to a login server that
# was started separately, and deploy.sh knows of no unit but the world and dev.
#
# Why that matters today rather than in general. LoginServer loads data/pack in its
# CONSTRUCTOR - InvType and VarPlayerType - and updateHiscores in that process reads varps by
# NAME. A login server left running across a deploy keeps the pack it started with, and the
# comment at that load says what happens when the ids no longer line up: every figure it
# writes is skipped in silence. It also reads and writes save files directly, which is the
# other half of what the wipe is moving.
#
# These two are booleans, not secrets, so they are printed as read.
if [ -f "$ENGINE/.env" ]; then
    login=$(grep -E "^[[:space:]]*LOGIN_SERVER=" "$ENGINE/.env" 2>/dev/null | head -1 | cut -d= -f2-)
    easy=$(grep -E "^[[:space:]]*EASY_STARTUP=" "$ENGINE/.env" 2>/dev/null | head -1 | cut -d= -f2-)
    note "LOGIN_SERVER=${login:-unset, so false}   EASY_STARTUP=${easy:-unset, so false}"
    case "${login:-}:${easy:-}" in
        true:true)
            note "in-process: the login, friend and logger workers run inside the world, so the"
            note "stop above takes them with it. Nothing more to do." ;;
        true:*)
            note "SEPARATE PROCESS. Stop it for the wipe, and make sure the deploy restarts it -"
            note "otherwise it serves the launch on the pack it held BEFORE the deploy, and"
            note "writes its hiscore figures with the old ids." ;;
        *)
            note "the world runs its own login thread, so there is no second process." ;;
    esac
fi
if command -v systemctl > /dev/null 2>&1; then
    units=$(systemctl list-units --type=service --state=running --no-legend --plain 2>/dev/null | grep -oE "(deathplateau|lostcity)[a-z-]*[.]service" | sort -u | xargs)
    note "running now: ${units:-none that name this server}"
fi

step "4. The wipe. Read the dry run, and decide about --orphans before the day"
cmd "cd $ENGINE && npx tsx tools/server/wipe.ts --profile $PROFILE"
cmd "cd $ENGINE && npx tsx tools/server/wipe.ts --profile $PROFILE --confirm"
note "An orphan save is a character whose account row is gone: unreachable until somebody"
note "registers that username, when the login server hands them whatever is in it. The dry"
note "run counts them, and they are LEFT ALONE unless you add --orphans."
note "Saves move to data/players/$PROFILE/wiped-<stamp>/ and all three databases are backed"
note "up first. Nothing is deleted."

if [ "$QUICK" = "1" ]; then
    note "(--quick: the dry run was not run)"
elif [ -d "$ENGINE" ]; then
    printf '\n'
    note "the wipe's own dry run follows. It changes nothing:"
    printf '\n'
    # CAPTURED, NOT PIPED STRAIGHT INTO sed. A pipeline reports the status of its LAST
    # command, so `wipe.ts | sed` always succeeded and the branch below never ran - which is
    # the one branch that matters, because the dry run REFUSING is the check.
    out=$( cd "$ENGINE" && npx tsx tools/server/wipe.ts --profile "$PROFILE" 2>&1 )
    rc=$?
    sed 's/^/      /' <<INDENTED
$out
INDENTED
    [ "$rc" -eq 0 ] || note "it exited $rc, and that IS the check - read it now, not on the day."
else
    note "no engine checkout at $ENGINE, so there is nothing to dry run here"
fi

step "5. The world back up, and looked at"
cmd "systemctl start $SERVICE"
cmd "journalctl -u $SERVICE -f"
note "Log in once as a player: the character is new, and the clerk owes them their tickets."
note "Then list something at the trading post and watch for the card in Discord. That path"
note "has only ever been proved with tools/market/cardpreview.ts --post, which deliberately"
note "skips the queue, the value threshold, and the hook the game itself fires."
if [ -f "$ENGINE/.env" ]; then
    # NAMES ONLY, NEVER VALUES. A webhook URL is a password - whoever holds it can post to that
    # channel as the server - and a diagnostic that prints one has published it to a terminal, a
    # scrollback, and whatever that terminal is being watched on.
    for name in MARKET_FEED_WEBHOOK MARKET_CARD_ICONS MARKET_FEED_MIN; do
        if grep -qE "^[[:space:]]*$name=." "$ENGINE/.env" 2>/dev/null; then
            note "$name: set"
        else
            note "$name: not set - the feed is off, or the cards come out with an empty slot"
        fi
    done
    # cut, then the quotes dotenv would have stripped: a quoted path read as a missing one.
    icons=$(grep -E "^[[:space:]]*MARKET_CARD_ICONS=" "$ENGINE/.env" 2>/dev/null | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')
    if [ -n "${icons:-}" ] && [ -d "$icons" ]; then
        note "icons: $(ls -1 "$icons" 2>/dev/null | wc -l | tr -d ' ') files in $icons"
    elif [ -n "${icons:-}" ]; then
        note "icons: nothing at $icons, so every card will have an empty slot"
    fi
fi

step "6. The website: publish the post, and take the wipe notice down"
cmd "git -C <your checkout> fetch origin && git -C <your checkout> log --oneline main..origin/launch-day"
cmd "git -C <your checkout> merge origin/launch-day && git push origin main"
cmd "$WEB/deploy/deploy-web.sh"
note "THE MERGE COMES FIRST, and from a machine that can push - this box only ever pulls."
note ""
note "IT IS NOT A FAST-FORWARD, and this line said --ff-only until launch morning. The"
note "branch was cut on 11 November; main has had three commits since (the staff panel, the"
note "webhook permissions fix, and a correction to the Helper copy), so main is no longer an"
note "ancestor of the branch and --ff-only exits without merging. Finding that out at 1pm,"
note "with the wipe done and the site still carrying a notice that has become false, is the"
note "worst moment available. It merges cleanly - checked with git merge-tree - and the log"
note "line above is there in --ff-only's place: read what is about to come in, then merge."
note ""
note "The launch-day branch does two things at once: it moves the launch post out of"
note "content/news/_pending so the site renders it, and it removes the wipe notice from the"
note "five pages that carry it (the front page, /start, /register, /hiscores, /player)."
note ""
note "WHY IT IS A BRANCH. Until the wipe has actually run, that notice is the only thing"
note "telling somebody arriving from a toplist that their account is about to be reset. On"
note "main it would go out with any deploy this week and take the warning with it; after the"
note "wipe it says the opposite of the truth. So it waits here until the wipe is done."
note ""
note "deploy-web.sh then pulls, builds, restarts, and posts the new news to Discord."
note "A failed build leaves the old site running and stops."
# As of the last fetch - nothing here touches the network.
if [ -d "$WEB/.git" ] && git -C "$WEB" rev-parse --verify --quiet origin/launch-day > /dev/null 2>&1; then
    if git -C "$WEB" merge-base --is-ancestor origin/launch-day origin/main 2>/dev/null; then
        note "launch-day: already merged into main"
    else
        note "launch-day: NOT merged yet - the post stays unpublished and the notice stays up"
    fi
fi
if [ -d "$WEB/content/news" ]; then
    latest=$(ls -1t "$WEB/content/news"/*.md 2> /dev/null | head -1)
    if [ -n "${latest:-}" ]; then note "newest post: $(basename "$latest")"; fi
    if [ -f "$WEB/.news-announced" ]; then
        note "announced so far: $(wc -l < "$WEB/.news-announced" 2>/dev/null | tr -d ' ') on record"
    else
        note "no $WEB/.news-announced yet, so the next deploy decides what counts as new"
    fi
fi

step "7. The staff roster panel in Discord. After the site, so the links in it work"
cmd "cd $WEB && node scripts/discord-panels.mjs staff --dry-run"
cmd "cd $WEB && node scripts/discord-panels.mjs staff"
note "The standing panel naming the owners, administrators and helpers, what each rank's"
note "icon looks like, and what staff will never ask a player for."
note ""
note "IT IS HELD UNTIL TODAY ON PURPOSE. It names Iron Sgt as a Helper, so posting it is"
note "also the announcement of that rank - and a roster posted before the wipe would be"
note "read by people whose accounts are about to reset."
note ""
note "It needs a webhook of its own, made in #rules: a SECOND one, beside the rules"
note "panel's, because the lookup is keyed on the panel name rather than the channel."
note "Save it as \$WEB/.discord-staff-webhook. deploy-web.sh puts every .discord-*-webhook"
note "back to root-only after its chown, so it stays out of the game process's reach."
note ""
note "KEEP THE MESSAGE ID IT PRINTS. Put it in the POSTED map in scripts/discord-panels.mjs"
note "and changing the roster later becomes --edit, which rewrites the panel in place and"
note "keeps its pin and position. Without the id, the only way to correct a name is to"
note "delete the message and post a new one, which loses both."
# Reads, like everything else here.
if [ -f "$WEB/.discord-staff-webhook" ]; then
    note "webhook: present"
else
    note "webhook: MISSING - make it in #rules and save it as $WEB/.discord-staff-webhook"
fi
if [ -f "$WEB/scripts/discord-panels.mjs" ]; then
    if grep -q "^    staff: '" "$WEB/scripts/discord-panels.mjs"; then
        note "posted already: there is a staff id in POSTED, so change it with --edit"
    else
        note "not posted yet: no staff id in POSTED"
    fi
fi

step "8. The Veteran rank. Whenever - it is safe with the world up"
cmd "cd $ENGINE && npx tsx tools/server/veteran.ts --profile $PROFILE"
cmd "cd $ENGINE && npx tsx tools/server/veteran.ts --profile $PROFILE --confirm"
note "Qualifies on a save file - live, or in any wiped-* folder - AND a registration before"
note "the cutoff, which is Eastern midnight on November 15 2026. It only ever grants, so"
note "running it again later picks up anybody missed without taking anything back."

printf '\n'
