#include "lru.h"

#include <algorithm>
#include <cassert>

lru::lru(CACHE* cache) : lru(cache, cache->NUM_SET, cache->NUM_WAY) {}

lru::lru(CACHE* cache, long sets, long ways) : replacement(cache), NUM_WAY(ways), last_used_cycles(static_cast<std::size_t>(sets * ways), 0) {}

def find_victim(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
def find_victim(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
{

            // Add your code here an improved cache replacement policy.
            
}


def replacement_cache_fill(int triggering_cpu, long set, long way, int full_addr, int ip, int victim_addr, int type) -> void:
void lru::replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr,
                                 access_type type)
{
  // Mark the way as being used on the current cycle
  last_used_cycles.at((std::size_t)(set * NUM_WAY + way)) = cycle++;
}


def update_replacement_state(int triggering_cpu, long set, long way, int full_addr, int ip, int victim_addr, int type, int hit) -> void:
void lru::update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                   champsim::address victim_addr, access_type type, uint8_t hit)
{
  // Mark the way as being used on the current cycle
  if (hit && access_type{type} != access_type::WRITE) // Skip this for writeback hits
    last_used_cycles.at((std::size_t)(set * NUM_WAY + way)) = cycle++;
}

