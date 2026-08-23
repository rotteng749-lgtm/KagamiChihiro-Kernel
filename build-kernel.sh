#!/usr/bin/env bash
# ============================================================================
#  KagamiChihiro GKI 5.10 Builder — Infinix Note 30 (X6833B / MT6789)
#  Base  : MillenniumOSS android_kernel_common_android12-5.10 (chihiro-rebase)
#  Root  : KernelSU-Next + SUSFS v2.2.0
#  Extra : NTSYNC, BBR3, CAKE, HZ_300, ZRAM, Yamada/Hololive feature set
#  Usage : ./build-kernel.sh            (auto, no args needed)
#  Output: ./out/AnyKernel3/*.zip       (flashable via recovery)
# ============================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

KERNEL_NAME="KagamiChihiro"
KERNEL_DEFCONFIG="gki_defconfig"
JOBS="${JOBS:-2}"                # RAM-limited machine -> keep low
OUT="$ROOT/out"
TC="$ROOT/toolchain/bin"
DEPS="$ROOT/.deps"
ANYKERNEL="$DEPS/AnyKernel3"

export PATH="$TC:$PATH"
export KBUILD_BUILD_USER="KanagawaYamada"
export KBUILD_BUILD_HOST="HoshimachiSuisei"

log() { echo -e "\033[1;36m[*]\033[0m $*"; }
die() { echo -e "\033[1;31m[!]\033[0m $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Toolchain check
# ---------------------------------------------------------------------------
command -v clang >/dev/null 2>&1 || die "clang not found. Run: sudo apt install clang-16 lld-16 llvm-16"
command -v ld.lld >/dev/null 2>&1 || die "ld.lld not found."
log "Toolchain: $(clang --version | head -1)"

# ---------------------------------------------------------------------------
# 2. KernelSU-Next wiring (idempotent — safe to re-run)
# ---------------------------------------------------------------------------
if [ ! -L drivers/kernelsu ]; then
  log "Wiring KernelSU-Next driver..."
  ln -sf "$ROOT/.deps/KernelSU-Next/kernel" drivers/kernelsu
  grep -q 'CONFIG_KSU' drivers/Makefile || printf '\nobj-$(CONFIG_KSU) += kernelsu/\n' >> drivers/Makefile
  grep -q 'drivers/kernelsu/Kconfig' drivers/Kconfig || sed -i '/endmenu/i\tsource "drivers/kernelsu/Kconfig"' drivers/Kconfig
else
  log "KernelSU-Next already wired."
fi

# ---------------------------------------------------------------------------
# 3. Generate config
# ---------------------------------------------------------------------------
rm -rf "$OUT"
log "Generating $KERNEL_DEFCONFIG ..."
make O="$OUT" ARCH=arm64 LLVM=1 LLVM_IAS=1 "$KERNEL_DEFCONFIG" 2>&1 | grep -vE '^scripts|^  CC|^  LD' || true

# ---------------------------------------------------------------------------
# 4. Build kernel
# ---------------------------------------------------------------------------
log "Building kernel with $JOBS jobs (this takes a while)..."
make O="$OUT" ARCH=arm64 LLVM=1 LLVM_IAS=1 -j"$JOBS" Image.gz 2>&1 | tee "$OUT/build.log" | grep -iE 'error|warning: |Kernel: arch' | tail -40

if [ ! -f "$OUT/arch/arm64/boot/Image.gz" ]; then
  die "Build failed — check $OUT/build.log"
fi
log "Kernel built: $(ls -lh "$OUT/arch/arm64/boot/Image.gz" | awk '{print $5}')"

# ---------------------------------------------------------------------------
# 5. AnyKernel3 packaging
# ---------------------------------------------------------------------------
PKG="$OUT/AnyKernel3"
rm -rf "$PKG"
mkdir -p "$PKG"
cp -r "$ANYKERNEL"/META-INF "$ANYKERNEL"/tools "$ANYKERNEL"/modules "$ANYKERNEL"/patch "$ANYKERNEL"/ramdisk "$PKG"/ 2>/dev/null || true
cp "$OUT/arch/arm64/boot/Image.gz" "$PKG/Image.gz"
cp "$ANYKERNEL/anykernel.sh" "$PKG/anykernel.sh"

# Zip it
cd "$PKG"
ZIP="$OUT/${KERNEL_NAME}-5.10.260-KernelSU-Next-SUSFS2.2.0.zip"
rm -f "$ZIP"
zip -r9 "$ZIP" . -x '*.git*' >/dev/null
cd "$ROOT"

log "=============================================="
log " FLASHABLE ZIP: $ZIP"
log " Size: $(ls -lh "$ZIP" | awk '{print $5}')"
log "=============================================="
