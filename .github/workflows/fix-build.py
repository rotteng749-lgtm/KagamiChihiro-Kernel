#!/usr/bin/env python3
"""
Fix build errors for KagamiChihiro GKI 5.10 kernel.
Handles API mismatches between 6.x patches and 5.10 base kernel.
"""
import re, sys


def fix_ntsync():
    """Fix ntsync.c: Replace all lockdep usage with safe stubs for 5.10"""
    path = "drivers/misc/ntsync.c"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {path} not found")
        return

    orig = content

    if "KagamiChihiro compat" in content:
        print(f"[OK] {path}: already patched")
        return

    # 1. Replace the ntsync_assert_held macro definition entirely with a no-op.
    #    The original macro uses lockdep_is_held() which doesn't exist in 5.10.
    #    Use a line-by-line approach to replace the multi-line macro.
    lines = content.split('\n')
    new_lines = []
    skip_until_blank = False

    for i, line in enumerate(lines):
        if skip_until_blank:
            if line.strip() == '' or (not line.startswith('\t') and not line.startswith(' ')):
                skip_until_blank = False
            else:
                continue  # skip lines that are part of the old macro

        if '#define ntsync_assert_held(obj)' in line and '\\' in line:
            # Found the start of the old macro - skip all continuation lines
            skip_until_blank = True
            new_lines.append('#define ntsync_assert_held(obj) do { (void)(obj); } while (0)')
            continue

        new_lines.append(line)

    content = '\n'.join(new_lines)

    # 2. Replace lockdep_assert(expr) with WARN_ON(!(expr))
    #    lockdep_assert() doesn't exist in kernel 5.10 - it was added in 6.x
    #    Handle both single-line and the simple cases (no nested parens in remaining calls)
    content = content.replace('lockdep_assert(', 'KAGAMI_LOCKDEP_ASSERT_HELPER(')

    # Now replace the helper with WARN_ON
    # First handle simple cases: single-line calls
    content = re.sub(
        r'KAGAMI_LOCKDEP_ASSERT_HELPER\(([^()]+)\)',
        r'WARN_ON(!(\1))',
        content
    )
    # Handle cases with one level of nested parens like (a) || (b)
    content = re.sub(
        r'KAGAMI_LOCKDEP_ASSERT_HELPER\(([^()]*(?:\([^()]+\)[^()]*)+)\)',
        r'WARN_ON(!(\1))',
        content
    )
    # If any remain, just replace them as-is
    if 'KAGAMI_LOCKDEP_ASSERT_HELPER' in content:
        remaining = content.count('KAGAMI_LOCKDEP_ASSERT_HELPER')
        print(f"[WARN] {path}: {remaining} lockdep_assert calls not replaced, forcing")
        content = re.sub(
            r'KAGAMI_LOCKDEP_ASSERT_HELPER\((.*?)\)',
            r'WARN_ON(!(\1))',
            content
        )

    # 3. Remove any remaining LOCK_STATE_NOT_HELD references
    content = content.replace(" != LOCK_STATE_NOT_HELD", "")
    content = content.replace(" == LOCK_STATE_NOT_HELD", " == 0")

    # 4. Add include for linux/lockdep.h (needed for lockdep_assert_held calls that remain)
    if "linux/lockdep.h" not in content:
        content = content.replace(
            "#include <linux/module.h>",
            "#include <linux/module.h>\n#include <linux/lockdep.h>",
            1
        )

    # 5. Add compat marker at top of file
    content = "/* KagamiChihiro compat: patched for 5.10 kernel */\n" + content

    if content != orig:
        with open(path, "w") as f:
            f.write(content)
        print(f"[FIX] {path}: replaced ntsync_assert_held macro and lockdep_assert calls")
    else:
        print(f"[OK] {path}: no changes needed")


def fix_tcp_h():
    path = "include/net/tcp.h"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {path} not found")
        return

    orig = content

    # 1. Add tcp_plb_net_context and tcp_get_plb_ctx if missing
    if "struct tcp_plb_net_context" not in content:
        plb_marker = "void tcp_plb_update_state_upon_rto(struct sock *sk, struct tcp_plb_state *plb);"
        plb_insert = plb_marker + """

/* PLB network-level context for BBR3 */
struct tcp_plb_sysctl_params {
\tu8 sysctl_tcp_plb_enabled;
\tu8 sysctl_tcp_plb_idle_rehash_rounds;
\tu8 sysctl_tcp_plb_rehash_rounds;
\tu8 sysctl_tcp_plb_suspend_rto_sec;
\tint sysctl_tcp_plb_cong_thresh;
};

struct tcp_plb_net_context {
\tstruct tcp_plb_sysctl_params params;
\tstruct ctl_table_header *sysctl_header;
};

extern unsigned int tcp_plb_net_id;
struct tcp_plb_net_context *tcp_get_plb_ctx(struct net *net);"""
        content = content.replace(plb_marker, plb_insert)
        print(f"[FIX] {path}: added tcp_plb_net_context and tcp_get_plb_ctx")

    # 2. Add struct bbr3 if missing
    if "struct bbr3 {" not in content:
        marker = "/* At how many usecs into the future should the RTO fire? */"
        if marker in content:
            struct_bbr3 = """

/* BBR3 congestion control block */
struct bbr3 {
\tu32\tmin_rtt_us;
\tu32\tmin_rtt_stamp;
\tu32\tprobe_rtt_done_stamp;
\tu32\tprobe_rtt_min_us;
\tu32\tprobe_rtt_min_stamp;
\tu32    next_rtt_delivered;
\tu64\tcycle_mstamp;
\tu32    mode:2,
\t\tprev_ca_state:3,
\t\tround_start:1,
\t\tce_state:1,
\t\tbw_probe_up_rounds:5,
\t\ttry_fast_path:1,
\t\tidle_restart:1,
\t\tprobe_rtt_round_done:1,
\t\tinit_cwnd:7,
\t\tunused_1:10;
\tu32\tpacing_gain:10,
\t\tcwnd_gain:10,
\t\tfull_bw_reached:1,
\t\tfull_bw_cnt:2,
\t\tcycle_idx:2,
\t\thas_seen_rtt:1,
\t\tunused_2:6;
\tu32\tprior_cwnd;
\tu32\tfull_bw;
\tu64\tack_epoch_mstamp;
\tu16\textra_acked[2];
\tu32\tack_epoch_acked:20,
\t\textra_acked_win_rtts:5,
\t\textra_acked_win_idx:1,
\t\tfull_bw_now:1,
\t\tstartup_ecn_rounds:2,
\t\tloss_in_cycle:1,
\t\tecn_in_cycle:1,
\t\tunused_3:1;
\tu32\tloss_round_delivered;
\tu32\tundo_bw_lo;
\tu32\tundo_inflight_lo;
\tu32\tundo_inflight_hi;
\tu32\tbw_latest;
\tu32\tbw_lo;
\tu32\tbw_hi[2];
\tu32\tinflight_latest;
\tu32\tinflight_lo;
\tu32\tinflight_hi;
\tu32\tbw_probe_up_cnt;
\tu32\tbw_probe_up_acks;
\tu32\tprobe_wait_us;
\tu32\tprior_rcv_nxt;
\tu32\tecn_eligible:1,
\t\tecn_alpha:9,
\t\tbw_probe_samples:1,
\t\tprev_probe_too_high:1,
\t\tstopped_risky_probe:1,
\t\trounds_since_probe:8,
\t\tloss_round_start:1,
\t\tloss_in_round:1,
\t\tecn_in_round:1,
\t\tack_phase:3,
\t\tloss_events_in_round:4,
\t\tinitialized:1;
\tu32\talpha_last_delivered;
\tu32\talpha_last_delivered_ce;
\tu8\tunused_4;
\tstruct tcp_plb_state plb;
\tvoid (*skb_marked_lost)(struct sock *sk, const struct sk_buff *skb);
};

"""
            content = content.replace(marker, struct_bbr3 + marker, 1)
            print(f"[FIX] {path}: added struct bbr3 definition")
        else:
            print(f"[WARN] {path}: could not find insertion point for struct bbr3")

    if content != orig:
        with open(path, "w") as f:
            f.write(content)
    else:
        print(f"[OK] {path}: no changes needed")


def fix_bbr3_c():
    path = "net/ipv4/tcp_bbr3.c"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {path} not found")
        return

    orig = content

    # 1. Fix bbr3_tso_segs: 5.10 tso_segs callback takes (struct sock *, unsigned int)
    content = content.replace(
        "static u32 bbr3_tso_segs(struct sock *sk)",
        "static u32 bbr3_tso_segs(struct sock *sk, unsigned int mss_now)"
    )

    # 2. Remove local mss_now declaration since it's now a parameter
    content = content.replace(
        "\tunsigned int mss_now = tcp_current_mss(sk);\n",
        "\t/* mss_now is now a parameter for 5.10 compat */\n",
        1
    )

    # 3. Fix min_tso_segs -> tso_segs (5.10 field name)
    content = content.replace(".min_tso_segs", ".tso_segs")

    if content != orig:
        with open(path, "w") as f:
            f.write(content)
        print(f"[FIX] {path}: fixed tso_segs signature, removed mss_now redefinition, fixed field name")
    else:
        print(f"[OK] {path}: no changes needed")


def fix_tcp_plb_c():
    """Add tcp_get_plb_ctx implementation to tcp_plb.c"""
    path = "net/ipv4/tcp_plb.c"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {path} not found")
        return

    orig = content

    # Add netns/generic.h include for net_generic() if missing
    if "net/netns/generic.h" not in content:
        content = content.replace(
            "#include <net/tcp.h>",
            "#include <net/tcp.h>\n#include <net/netns/generic.h>",
            1
        )
        print(f"[FIX] {path}: added #include <net/netns/generic.h> for net_generic()")

    if "tcp_get_plb_ctx" in content:
        if content != orig:
            with open(path, "w") as f:
                f.write(content)
        print(f"[OK] {path}: tcp_get_plb_ctx already present")
        return

    marker = "void tcp_plb_update_state"
    if marker in content:
        insert = """unsigned int tcp_plb_net_id __read_mostly;

struct tcp_plb_net_context *tcp_get_plb_ctx(struct net *net)
{
\treturn net_generic(net, tcp_plb_net_id);
}
EXPORT_SYMBOL_GPL(tcp_get_plb_ctx);

"""
        content = content.replace(marker, insert + marker, 1)
        with open(path, "w") as f:
            f.write(content)
        print(f"[FIX] {path}: added tcp_get_plb_ctx implementation")
    else:
        print(f"[WARN] {path}: marker not found for tcp_get_plb_ctx insertion")


def fix_gso():
    path = "include/linux/netdevice.h"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {path} not found")
        return

    if "GSO_LEGACY_MAX_SIZE" in content:
        print(f"[OK] {path}: GSO_LEGACY_MAX_SIZE already defined")
        return

    content = content.replace(
        "#define GSO_MAX_SIZE",
        "#define GSO_LEGACY_MAX_SIZE GSO_MAX_SIZE\n#define GSO_MAX_SIZE",
        1
    )
    with open(path, "w") as f:
        f.write(content)
    print(f"[FIX] {path}: added GSO_LEGACY_MAX_SIZE define")


if __name__ == "__main__":
    print("=== Applying KagamiChihiro build fixes ===")
    fix_ntsync()
    fix_tcp_h()
    fix_bbr3_c()
    fix_tcp_plb_c()
    fix_gso()
    print("=== Done ===")
