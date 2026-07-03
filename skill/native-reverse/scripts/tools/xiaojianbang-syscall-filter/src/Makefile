# xiaojianbang-syscall-filter KPM Makefile
#
# 作者：小肩膀   微信：xiaojianbang8888
#
# 重要：KPM 必须用 clang 的 large code model 编译，产生 R_AARCH64_MOVW_UABS_G*
# 绝对寻址重定位（KernelPatch relo.c 支持）。
#   - GCC(aarch64-linux-gnu) 默认 -fPIC 会产生 GOT 重定位 -> relo.c 不支持，加载失败
#   - GCC -mcmodel=large -fno-pic 会残留 ADR_PREL_PG_HI21 -> 加载到内核高地址时 overflow
#   - clang --target=aarch64-none-elf -mcmodel=large -fno-pic 才产生纯 MOVW_UABS，正确
#
# 用法：
#   make CLANG=/path/to/clang LD_LLD=/path/to/ld.lld
# 或直接用默认的 AOSP clang 路径。

KP_DIR ?= ../../KernelPatch-main

# 默认使用 AOSP 自带 clang（已验证 r522817 可用）
CLANG  ?= /home/xiaojianbang/bin/aosp/prebuilts/clang/host/linux-x86/clang-r522817/bin/clang
LD_LLD ?= /home/xiaojianbang/bin/aosp/prebuilts/clang/host/linux-x86/clang-r522817/bin/ld.lld

INCLUDE_DIRS := . include patch/include linux/include linux/arch/arm64/include linux/tools/arch/arm64/include
INCLUDE_FLAGS := $(foreach dir,$(INCLUDE_DIRS),-I$(KP_DIR)/kernel/$(dir))

CFLAGS := --target=aarch64-none-elf \
          -mcmodel=large -fno-pic \
          -fno-stack-protector \
          -fno-asynchronous-unwind-tables -fno-unwind-tables \
          -ffreestanding -fno-builtin -nostdlib \
          -O2 -Wall

objs := syscallhook.o

all: syscallhook.kpm ../syscallhook.kpm

syscallhook.kpm: $(objs)
	$(LD_LLD) -r -o $@ $^

../syscallhook.kpm: syscallhook.kpm
	cp $< $@

%.o: %.c
	$(CLANG) $(CFLAGS) $(INCLUDE_FLAGS) -c -o $@ $<

.PHONY: clean
clean:
	rm -f *.kpm *.o ../syscallhook.kpm
