#!/usr/bin/env python3
"""
Package AnyKernel3 zip for KagamiChihiro kernel.
Creates a flashable zip with proper anykernel.sh for GKI devices.
Supports dynamic naming from environment variables.
"""
import os
import subprocess
import sys

# Read from environment (set by each workflow)
KERNEL_VERSION = os.environ.get("KERNEL_VERSION", "5.10.264")
CLANG_VERSION = os.environ.get("CLANG_VERSION", "0")
BUILD_LABEL = os.environ.get("BUILD_LABEL", "unknown")

if CLANG_VERSION != "0":
    ZIP_NAME = f"KagamiChihiro-{KERNEL_VERSION}-Clang{CLANG_VERSION}-{BUILD_LABEL}.zip"
else:
    ZIP_NAME = f"KagamiChihiro-{KERNEL_VERSION}.zip"

AK3_DIR = ".deps/AnyKernel3"
PKG_DIR = "out/AnyKernel3"

ANYKERNEL_SH = f"""### AnyKernel3 Ramdisk Mod Script
## osm0sis @ xda-developers

### AnyKernel setup
# global properties
properties() {{ '
kernel.string=KagamiChihiro {KERNEL_VERSION} (Clang {CLANG_VERSION} {BUILD_LABEL})
do.devicecheck=0
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=
device.name2=
device.name3=
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; }} # end properties

### AnyKernel install
## boot shell variables
BLOCK=boot;
IS_SLOT_DEVICE=auto;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching - see for reference (DO NOT REMOVE)
. tools/ak3-core.sh;

ui_print " "
ui_print "KagamiChihiro Kernel {KERNEL_VERSION}"
ui_print "Compiler: Clang {CLANG_VERSION} ({BUILD_LABEL})"
ui_print "Target: Infinix Note 30 (X6833B / MT6789)"
ui_print " "

# boot install
if [ -L "/dev/block/bootdevice/by-name/init_boot_a" -o -L "/dev/block/by-name/init_boot_a" ]; then
    split_boot
    flash_boot
else
    dump_boot
    write_boot
fi
"""


def main():
    print(f"Packaging: {ZIP_NAME}")

    # Clone AnyKernel3 if not present
    if not os.path.isdir(AK3_DIR):
        subprocess.run(
            ["git", "clone", "--depth=1", "https://github.com/osm0sis/AnyKernel3.git", AK3_DIR],
            check=True,
        )
        print(f"Cloned AnyKernel3 to {AK3_DIR}")

    # Clean and create package dir
    if os.path.exists(PKG_DIR):
        subprocess.run(["rm", "-rf", PKG_DIR], check=True)
    subprocess.run(["cp", "-r", AK3_DIR, PKG_DIR], check=True)

    # Copy kernel images
    for img in ["Image", "Image.gz"]:
        src = f"out/arch/arm64/boot/{img}"
        dst = f"{PKG_DIR}/{img}"
        if os.path.exists(src):
            subprocess.run(["cp", src, dst], check=True)
            print(f"Copied {src} -> {dst}")
        else:
            print(f"WARNING: {src} not found!")

    # Write custom anykernel.sh
    with open(f"{PKG_DIR}/anykernel.sh", "w") as f:
        f.write(ANYKERNEL_SH)
    print(f"Wrote {PKG_DIR}/anykernel.sh")

    # Create zip
    os.chdir(PKG_DIR)
    subprocess.run(
        ["zip", "-r9", f"../{ZIP_NAME}", ".", "-x", "*.git*", "-x", "*.placeholder"],
        check=True,
    )
    os.chdir("../..")

    zip_path = f"out/{ZIP_NAME}"
    if os.path.exists(zip_path):
        size = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"Zip created: {zip_path} ({size:.1f} MB)")
    else:
        print(f"ERROR: {zip_path} not created!")
        sys.exit(1)


if __name__ == "__main__":
    main()
