#!/usr/bin/env python3
"""
Fix build errors for KagamiChihiro GKI 5.10 kernel.

Issues:
1. ntsync.c uses lockdep_assert() — not available in 5.10, should be lockdep_assert_held()
2. ntsync.c uses LOCK_STATE_NOT_HELD — not available in 5.10
3. include/net/tcp.h missing struct bbr3 definition (patch didn't apply fully)
4. GSO_LEGACY_MAX_SIZE not defined in 5.10
"""
import re, sys

def fix_ntsync():
    path = "drivers/misc/ntsync.c"
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[SKIP] {path} not found")
        return

    orig = content

    # 1. lockdep_assert() -> lockdep_assert_held()
    content = content.replace("lockdep_assert(", "lockdep_assert_held(")

    # 2. Remove LOCK_STATE_NOT_HELD comparisons
    content = content.replace(" != LOCK_STATE_NOT_HELD", "")

    # 3. Add lockdep.h include if missing
    if "linux/lockdep.h" not in content:
        content = content.replace(
            "#include <linux/module.h>",
            "#include <linux/module.h>\n#include <linux/lockdep.h>",
            1
        )

    if content != orig:
        with open(path, "w") as f:
            f.write(content)
        print(f"[FIX] {path}: lockdep_assert -> lockdep_assert_held, removed LOCK_STATE_NOT_HELD")
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

    if "struct bbr3 {" in content:
        print(f"[OK] {path}: struct bbr3 already present")
        return

    marker = "void tcp_plb_update_state_upon_rto(struct sock *sk, struct tcp_plb_state *plb);"
    if marker not in content:
        print(f"[WARN] {path}: marker not found, skipping struct bbr3 insertion")
        return

    struct_bbr3 = r"""

/* BBR3 congestion control block */
struct bbr3 {
	u32	min_rtt_us;	        /* min RTT in min_rtt_win_sec window */
	u32	min_rtt_stamp;	        /* timestamp of min_rtt_us */
	u32	probe_rtt_done_stamp;   /* end time for BBR_PROBE_RTT mode */
	u32	probe_rtt_min_us;	/* min RTT in probe_rtt_win_ms win */
	u32	probe_rtt_min_stamp;	/* timestamp of probe_rtt_min_us */
	u32     next_rtt_delivered;    /* scb->tx.delivered at end of round */
	u64	cycle_mstamp;	     /* time of this cycle phase start */
	u32     mode:2,		     /* current bbr_mode in state machine */
		prev_ca_state:3,     /* CA state on previous ACK */
		round_start:1,	     /* start of packet-timed tx->ack round? */
		ce_state:1,          /* If most recent data has CE bit set */
		bw_probe_up_rounds:5,/* cwnd-limited rounds in PROBE_UP */
		try_fast_path:1,     /* can we take fast path? */
		idle_restart:1,	     /* restarting after idle? */
		probe_rtt_round_done:1,  /* a BBR_PROBE_RTT round at 4 pkts? */
		init_cwnd:7,         /* initial cwnd */
		unused_1:10;
	u32	pacing_gain:10,	/* current gain for setting pacing rate */
		cwnd_gain:10,	/* current gain for setting cwnd */
		full_bw_reached:1,   /* reached full bw in Startup? */
		full_bw_cnt:2,	/* number of rounds without large bw gains */
		cycle_idx:2,	/* current index in pacing_gain cycle array */
		has_seen_rtt:1, /* have we seen an RTT sample yet? */
		unused_2:6;
	u32	prior_cwnd;	/* prior cwnd upon entering loss recovery */
	u32	full_bw;	/* recent bw, to estimate if pipe is full */

	/* For tracking ACK aggregation: */
	u64	ack_epoch_mstamp;	/* start of ACK sampling epoch */
	u16	extra_acked[2];		/* max excess data ACKed in epoch */
	u32	ack_epoch_acked:20,	/* packets (S)ACKed in sampling epoch */
		extra_acked_win_rtts:5,	/* age of extra_acked, in round trips */
		extra_acked_win_idx:1,	/* current index in extra_acked array */
	/* BBR v3 state: */
		full_bw_now:1,		/* recently reached full bw plateau? */
		startup_ecn_rounds:2,	/* consecutive hi ECN STARTUP rounds */
		loss_in_cycle:1,	/* packet loss in this cycle? */
		ecn_in_cycle:1,		/* ECN in this cycle? */
		unused_3:1;
	u32	loss_round_delivered; /* scb->tx.delivered ending loss round */
	u32	undo_bw_lo;	     /* bw_lo before latest losses */
	u32	undo_inflight_lo;    /* inflight_lo before latest losses */
	u32	undo_inflight_hi;    /* inflight_hi before latest losses */
	u32	bw_latest;	 /* max delivered bw in last round trip */
	u32	bw_lo;		 /* lower bound on sending bandwidth */
	u32	bw_hi[2];	 /* max recent measured bw sample */
	u32	inflight_latest; /* max delivered data in last round trip */
	u32	inflight_lo;	 /* lower bound of inflight data range */
	u32	inflight_hi;	 /* upper bound of inflight data range */
	u32	bw_probe_up_cnt; /* packets delivered per inflight_hi incr */
	u32	bw_probe_up_acks;  /* packets (S)ACKed since inflight_hi incr */
	u32	probe_wait_us;	 /* PROBE_DOWN until next clock-driven probe */
	u32	prior_rcv_nxt;	/* tp->rcv_nxt when CE state last changed */
	u32	ecn_eligible:1,	/* sender can use ECN (RTT, handshake)? */
		ecn_alpha:9,	/* EWMA delivered_ce/delivered; 0..256 */
		bw_probe_samples:1,    /* rate samples reflect bw probing? */
		prev_probe_too_high:1, /* did last PROBE_UP go too high? */
		stopped_risky_probe:1, /* last PROBE_UP stopped due to risk? */
		rounds_since_probe:8,  /* packet-timed rounds since probed bw */
		loss_round_start:1,    /* loss_round_delivered round trip? */
		loss_in_round:1,       /* loss marked in this round trip? */
		ecn_in_round:1,	       /* ECN marked in this round trip? */
		ack_phase:3,	       /* bbr_ack_phase: meaning of ACKs */
		loss_events_in_round:4,/* losses in STARTUP round */
		initialized:1;	       /* has bbr_init() been called? */
	u32	alpha_last_delivered;	 /* tp->delivered at alpha update */
	u32	alpha_last_delivered_ce; /* tp->delivered_ce at alpha update */

	u8	unused_4;		/* to preserve alignment */
	struct tcp_plb_state plb;

	/* react to a specific lost skb (optional) */
	void (*skb_marked_lost)(struct sock *sk, const struct sk_buff *skb);
};

"""

    content = content.replace(marker, marker + struct_bbr3)
    with open(path, "w") as f:
        f.write(content)
    print(f"[FIX] {path}: added struct bbr3 definition")


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
    fix_gso()
    print("=== Done ===")
