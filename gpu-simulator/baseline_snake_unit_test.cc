#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <string>
#include <utility>
#include <vector>

#include "abstract_hardware_model.h"
#include "gpgpu-sim/gpu-cache.h"
#include "gpgpu-sim/baseline_snake.h"

void register_ptx_function(const char *name, function_info *impl) {
  (void)name;
  (void)impl;
}

namespace {

class snake_test_core_config_t : public core_config {
 public:
  snake_test_core_config_t() : core_config(nullptr) { init(); }

  void init() override {
    m_valid = true;
    warp_size = 32;
    gpgpu_coalesce_arch = 0;
    mem_warp_parts = 1;
    mem_unit_ports = 1;
    gpgpu_cache_texl1_linesize = 128;
    gpgpu_cache_constl1_linesize = 128;
    gpgpu_max_insn_issue_per_warp = 1;
    gmem_skip_L1D = false;
    adaptive_cache_config = false;
  }
};

class inspectable_snake_prefetcher_t : public baseline_snake_prefetcher_t {
 public:
  using baseline_snake_prefetcher_t::baseline_snake_prefetcher_t;
  using baseline_snake_prefetcher_t::on_instruction_issue_with_cta;

  size_t queued_prefetches() const { return m_prefetch_queue.size(); }
  void clear_prefetches() { m_prefetch_queue.clear(); }
  new_addr_type queued_addr(size_t index) const { return m_prefetch_queue[index].addr; }
};

warp_inst_t make_global_load(const core_config &config, new_addr_type pc,
                             std::initializer_list<new_addr_type> addrs) {
  warp_inst_t inst(&config);
  inst.pc = pc;
  inst.op = LOAD_OP;
  inst.memory_op = memory_load;
  inst.space = memory_space_t(global_space);

  active_mask_t active_mask;
  unsigned lane = 0;
  for (new_addr_type addr : addrs) {
    active_mask.set(lane);
    inst.set_addr(lane, addr);
    ++lane;
  }
  inst.set_active(active_mask);
  return inst;
}

warp_inst_t make_global_load_with_lanes(
    const core_config &config, new_addr_type pc,
    std::initializer_list<std::pair<unsigned, new_addr_type>> lane_addrs) {
  warp_inst_t inst(&config);
  inst.pc = pc;
  inst.op = LOAD_OP;
  inst.memory_op = memory_load;
  inst.space = memory_space_t(global_space);

  active_mask_t active_mask;
  for (const auto &lane_addr : lane_addrs) {
    active_mask.set(lane_addr.first);
    inst.set_addr(lane_addr.first, lane_addr.second);
  }
  inst.set_active(active_mask);
  return inst;
}

bool expect_true(bool condition, const char *message) {
  if (!condition) {
    std::fprintf(stderr, "FAIL: %s\n", message);
    return false;
  }
  return true;
}

std::string capture_stats(const baseline_snake_prefetcher_t &snake) {
  char *buffer = nullptr;
  size_t buffer_size = 0;
  FILE *fp = open_memstream(&buffer, &buffer_size);
  if (!fp) return "";
  snake.print_stats(fp);
  fclose(fp);
  const std::string output(buffer ? buffer : "");
  free(buffer);
  return output;
}

bool test_default_config_uses_paper_head_table_size() {
  const baseline_snake_config_t snake_cfg;
  return expect_true(
      snake_cfg.ht_size == 32,
      "default Snake config should use a 32-entry head-sized PC table");
}

bool test_non_uniform_warp_is_filtered() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 2;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();

  const new_addr_type pc = 0x1000;
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc, {0x100, 0x200, 0x310}), 10);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc, {0x120, 0x250, 0x390}), 20);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc, {0x140, 0x2A0, 0x410}), 30);

  return expect_true(
      snake.queued_prefetches() == 0,
      "non-uniform warp should not train or issue Snake prefetches");
}

bool test_inter_warp_prefetch_requires_same_cta() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 2;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();

  const new_addr_type pc = 0x2000;
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc, {0x100}), 10);
  snake.on_instruction_issue_with_cta(
      1, 1, make_global_load(config, pc, {0x120}), 20);
  snake.on_instruction_issue_with_cta(
      2, 2, make_global_load(config, pc, {0x140}), 30);

  return expect_true(
      snake.queued_prefetches() == 0,
      "inter-warp Snake training must ignore accesses from different CTAs");
}

bool test_inter_thread_chain_prefetch_follows_configured_depth() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 3;
  snake_cfg.max_chain_length = 2;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();

  const new_addr_type pc_a = 0x3000;
  const new_addr_type pc_b = 0x3010;
  const new_addr_type pc_c = 0x3020;

  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_a, {0x100}), 10);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_b, {0x120}), 11);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_c, {0x140}), 12);

  snake.on_instruction_issue_with_cta(
      1, 0, make_global_load(config, pc_a, {0x550}), 20);
  snake.on_instruction_issue_with_cta(
      1, 0, make_global_load(config, pc_b, {0x570}), 21);
  snake.on_instruction_issue_with_cta(
      1, 0, make_global_load(config, pc_c, {0x590}), 22);

  snake.on_instruction_issue_with_cta(
      2, 0, make_global_load(config, pc_a, {0xA70}), 30);
  snake.on_instruction_issue_with_cta(
      2, 0, make_global_load(config, pc_b, {0xA90}), 31);
  snake.on_instruction_issue_with_cta(
      2, 0, make_global_load(config, pc_c, {0xAB0}), 32);

  snake.clear_prefetches();
  snake.on_instruction_issue_with_cta(
      3, 0, make_global_load(config, pc_a, {0xFB0}), 40);

  const bool depth_ok =
      snake.queued_prefetches() == 2 &&
      snake.queued_addr(0) == 0xFD0 &&
      snake.queued_addr(1) == 0xFF0;
  return expect_true(
      depth_ok,
      "inter-thread Snake chain should prefetch PC2 and PC3 addresses");
}

bool test_inter_warp_prefetch_uses_learned_stride_without_fixed_lookahead() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 2;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();

  const new_addr_type pc = 0x4000;
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc, {0x100}), 10);
  snake.on_instruction_issue_with_cta(
      1, 0, make_global_load(config, pc, {0x120}), 20);
  snake.on_instruction_issue_with_cta(
      2, 0, make_global_load(config, pc, {0x140}), 30);

  const bool lookahead_ok =
      snake.queued_prefetches() == 1 && snake.queued_addr(0) == 0x160;
  return expect_true(
      lookahead_ok,
      "inter-warp Snake prefetch should use the learned stride, not a fixed 16-step heuristic");
}

bool test_print_stats_reports_paper_style_demand_denominator() {
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 2;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_demand_load(0, 0x5000, 0x600, 10, HIT, nullptr);
  snake.on_demand_load(1, 0x5008, 0x620, 20, HIT, nullptr);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("coverage_paper=0.000000 accuracy_paper=0.000000 demand_loads=2 predicted_requests=0 timely_correct=0") !=
          std::string::npos,
      "Snake stats should report paper-style demand-load denominator");
}

bool test_print_stats_reports_pc_table_evictions() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 1;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 2;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, 0x6000, {0x100}), 10);
  snake.on_instruction_issue_with_cta(
      1, 0, make_global_load(config, 0x6010, {0x120}), 20);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("table_allocations=2 table_evictions=1") !=
          std::string::npos,
      "Snake stats should expose PC-table churn through allocation/eviction counters");
}

bool test_sparse_affine_active_lanes_are_accepted() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 1;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_instruction_issue_with_cta(
      0, 0,
      make_global_load_with_lanes(config, 0x7000,
                                  {{0, 0x100}, {2, 0x140}, {4, 0x180}}),
      10);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("issue_global_loads=1 uniform_gate_passes=1 uniform_gate_rejects=0") !=
              std::string::npos &&
          output.find("uniform_gate_pass_single_active=0 uniform_gate_pass_affine=1") !=
          std::string::npos,
      "affine active-lane gaps should still pass the Snake uniform-lane gate");
}

bool test_single_active_lane_is_classified_as_pass() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 1;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, 0x7050, {0x180}), 10);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("uniform_gate_pass_single_active=1 uniform_gate_pass_affine=0") !=
          std::string::npos,
      "single-active-lane loads should be classified as a distinct uniform-gate pass reason");
}

bool test_mixed_stride_is_classified_as_reject() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 1;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, 0x7060, {0x100, 0x120, 0x160}), 10);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("uniform_gate_reject_mixed_stride=1 uniform_gate_reject_non_affine=0") !=
              std::string::npos &&
          output.find("BASELINE_SNAKE_GATE_SAMPLE SM0: pc=0x7060 reason=mixed_stride active_count=3 first_lane=0 last_lane=2") !=
              std::string::npos,
      "mixed-stride loads should be classified separately and recorded in gate samples");
}

bool test_non_affine_progression_is_classified_as_reject() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 1;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_instruction_issue_with_cta(
      0, 0,
      make_global_load_with_lanes(config, 0x7070,
                                  {{0, 0x100}, {2, 0x140}, {5, 0x190}}),
      10);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("uniform_gate_reject_mixed_stride=0 uniform_gate_reject_non_affine=1") !=
              std::string::npos &&
          output.find("BASELINE_SNAKE_GATE_SAMPLE SM0: pc=0x7070 reason=non_affine_progression active_count=3 first_lane=0 last_lane=5") !=
              std::string::npos,
      "non-affine active-lane progressions should be classified separately and recorded in gate samples");
}

bool test_non_uniform_reject_keeps_tracker_history_for_it_chain() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 1;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();

  const new_addr_type pc_a = 0x7100;
  const new_addr_type pc_b = 0x7110;
  const new_addr_type pc_irregular = 0x7120;

  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_a, {0x100}), 10);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_irregular, {0x150, 0x260, 0x380}), 11);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_b, {0x120}), 12);

  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_a, {0x200}), 20);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_irregular, {0x250, 0x360, 0x480}), 21);
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_b, {0x220}), 22);

  snake.clear_prefetches();
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, pc_a, {0x340}), 30);

  const bool chain_ok =
      snake.queued_prefetches() == 1 && snake.queued_addr(0) == 0x360;
  return expect_true(
      chain_ok,
      "rejecting a non-uniform warp should not erase prior tracker history needed for IT chain learning");
}

bool test_print_stats_reports_uniform_gate_counters() {
  snake_test_core_config_t config;
  baseline_snake_config_t snake_cfg;
  snake_cfg.enable = true;
  snake_cfg.ht_size = 8;
  snake_cfg.training_warps = 1;
  snake_cfg.max_chain_length = 1;

  inspectable_snake_prefetcher_t snake(0, snake_cfg, nullptr);
  snake.on_kernel_launch();
  snake.on_instruction_issue_with_cta(
      0, 0, make_global_load(config, 0x7200, {0x100}), 10);
  snake.on_instruction_issue_with_cta(
      0, 0,
      make_global_load_with_lanes(config, 0x7210,
                                  {{0, 0x140}, {2, 0x1A0}, {5, 0x250}}),
      11);

  const std::string output = capture_stats(snake);
  if (output.empty()) {
    return expect_true(false, "open_memstream failed");
  }
  return expect_true(
      output.find("issue_global_loads=2 uniform_gate_passes=1 uniform_gate_rejects=1 uniform_gate_reject_kept_tracker=1") !=
              std::string::npos &&
          output.find("uniform_gate_pass_single_active=1 uniform_gate_pass_affine=0") !=
              std::string::npos &&
          output.find("uniform_gate_reject_mixed_stride=0 uniform_gate_reject_non_affine=1") !=
              std::string::npos &&
          output.find("uniform_gate_active_threads_total=4 uniform_gate_multi_active_total=1") !=
          std::string::npos,
      "Snake stats should report issue-time uniform-gate reason counters, activity totals, and preserved tracker rejects");
}

}  // namespace

int main() {
  if (!test_default_config_uses_paper_head_table_size()) return 1;
  if (!test_non_uniform_warp_is_filtered()) return 1;
  if (!test_inter_warp_prefetch_requires_same_cta()) return 1;
  if (!test_inter_thread_chain_prefetch_follows_configured_depth()) return 1;
  if (!test_inter_warp_prefetch_uses_learned_stride_without_fixed_lookahead()) return 1;
  if (!test_print_stats_reports_paper_style_demand_denominator()) return 1;
  if (!test_print_stats_reports_pc_table_evictions()) return 1;
  if (!test_sparse_affine_active_lanes_are_accepted()) return 1;
  if (!test_single_active_lane_is_classified_as_pass()) return 1;
  if (!test_mixed_stride_is_classified_as_reject()) return 1;
  if (!test_non_affine_progression_is_classified_as_reject()) return 1;
  if (!test_non_uniform_reject_keeps_tracker_history_for_it_chain()) return 1;
  if (!test_print_stats_reports_uniform_gate_counters()) return 1;
  std::puts("PASS: baseline_snake_unit_test");
  return 0;
}
