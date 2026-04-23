#include <cstdio>
#include <string>

#include "trace-parser/trace_parser.h"

namespace {

bool expect_true(bool condition, const char *message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    return false;
  }
  return true;
}

bool expect_addr(const inst_trace_t &inst, unsigned lane, uint64_t expected,
                 const char *message) {
  if (inst.memadd_info == nullptr) {
    std::fprintf(stderr, "FAIL: %s (memadd_info missing)\n", message);
    return false;
  }
  if (inst.memadd_info->addrs[lane] != expected) {
    std::fprintf(stderr,
                 "FAIL: %s (lane %u expected 0x%llx got 0x%llx)\n",
                 message, lane, static_cast<unsigned long long>(expected),
                 static_cast<unsigned long long>(inst.memadd_info->addrs[lane]));
    return false;
  }
  return true;
}

bool test_base_delta_sparse_two_active_lanes() {
  inst_trace_t inst;
  const std::string trace =
      "0090 00010001 1 R12 LDG.E.SYS 1 R8 4 2 0x100 256 42";
  if (!inst.parse_from_string(trace, 3, 0)) {
    return expect_true(false, "parse_from_string should succeed for sparse base-delta trace");
  }
  return expect_true(inst.memadd_info != nullptr,
                     "sparse base-delta trace should allocate memadd_info") &&
         expect_addr(inst, 0, 0x100, "sparse base-delta should keep first active lane address") &&
         expect_addr(inst, 16, 0x200, "sparse base-delta should reconstruct later active lane from one delta") &&
         expect_addr(inst, 1, 0, "inactive lanes should remain zero after sparse base-delta decode") &&
         expect_true(inst.imm == 42,
                     "sparse base-delta decode should not consume the trailing imm field");
}

bool test_base_delta_multi_active_lanes() {
  inst_trace_t inst;
  const std::string trace =
      "0180 0000001c 1 R3 LDG.E.SYS 1 R2 4 2 0x300 32 64 77";
  if (!inst.parse_from_string(trace, 3, 0)) {
    return expect_true(false, "parse_from_string should succeed for multi-active base-delta trace");
  }
  return expect_true(inst.memadd_info != nullptr,
                     "multi-active base-delta trace should allocate memadd_info") &&
         expect_addr(inst, 2, 0x300, "multi-active base-delta should keep the first active lane address") &&
         expect_addr(inst, 3, 0x320, "multi-active base-delta should apply the first delta once") &&
         expect_addr(inst, 4, 0x360, "multi-active base-delta should chain deltas across later active lanes") &&
         expect_addr(inst, 1, 0, "inactive lanes before first active lane should remain zero") &&
         expect_true(inst.imm == 77,
                     "multi-active base-delta decode should leave the trailing imm intact");
}

bool test_base_delta_single_active_lane_keeps_imm() {
  inst_trace_t inst;
  const std::string trace =
      "0190 00000001 1 R7 LDG.E.SYS 1 R6 4 2 0x500 99";
  if (!inst.parse_from_string(trace, 3, 0)) {
    return expect_true(false, "parse_from_string should succeed for single-active base-delta trace");
  }
  return expect_true(inst.memadd_info != nullptr,
                     "single-active base-delta trace should allocate memadd_info") &&
         expect_addr(inst, 0, 0x500, "single-active base-delta should keep the base address") &&
         expect_addr(inst, 1, 0, "single-active base-delta should leave inactive lanes empty") &&
         expect_true(inst.imm == 99,
                     "single-active base-delta decode should not consume imm as a fake delta");
}

}  // namespace

int main() {
  if (!test_base_delta_sparse_two_active_lanes()) return 1;
  if (!test_base_delta_multi_active_lanes()) return 1;
  if (!test_base_delta_single_active_lane_keeps_imm()) return 1;
  std::puts("PASS: trace_parser_unit_test");
  return 0;
}
