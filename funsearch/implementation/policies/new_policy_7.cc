#include "lru.h"

#include <algorithm>
#include <cassert>

lru::lru(CACHE* cache) : lru(cache, cache->NUM_SET, cache->NUM_WAY) {}

lru::lru(CACHE* cache, long sets, long ways) : replacement(cache), NUM_WAY(ways), last_used_cycles(static_cast<std::size_t>(sets * ways), 0) {}

def find_victim(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
<|begin_of_text|>System: You are a code generation assistant that is an expert on writing cache replacement policies. I need you to make a cache replacement policy for a cache simulator that maxmimzes the cache hit rate. Below I've provide some examples of policies and then a new policy for you to fill out with an improved version. Write out the C++ code for the new improved policy to improve on the existing policies. Only write one new policy inside the function skeleton that I provided for you at the end of the code. Code: #include "lru.h"

#include <algorithm>
#include <cassert>

lru::lru(CACHE* cache) : lru(cache, cache->NUM_SET, cache->NUM_WAY) {}

lru::lru(CACHE* cache, long sets, long ways) : replacement(cache), NUM_WAY(ways), last_used_cycles(static_cast<std::size_t>(sets * ways), 0) {}

def find_victim_v0(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> int:
def find_victim_v0(uint32_t triggering_cpu, uint64_t instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
long drrip::find_victim_v0(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                        champsim::address full_addr, access_type type)
{
  // look for the maxRRPV line
  auto begin = std::next(std::begin(rrpv), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);

  auto victim = std::max_element(begin, end);
  if (auto rrpv_update = maxRRPV - *victim; rrpv_update!= 0)
    for (auto it = begin; it!= end; ++it)
      *it += rrpv_update;

  assert(begin <= victim);
  assert(victim < end);
  return std::distance(begin, victim); // cast protected by assertions
}


def find_victim_v1(int tid, int setIndex, const int * current_set, int assoc, int PC, int paddr, int accessType) -> int:
def find_victim_v1(int tid, int setIndex, const int * current_set, int assoc, int PC, int paddr, int accessType) -> int:
int find_victim_v1 ( uint32_t tid, uint32_t setIndex, const BLOCK *current_set, uint32_t assoc, uint64_t PC, uint64_t paddr, uint32_t accessType) {

 // select a victim using default pseudo LRU policy

 assert (setIndex < llc_sets);
 int r;
 if (dan_use_rrip) {
startover:
  int lrus[LLC_WAYS], n = 0;
  for (unsigned int wayID=0; wayID<assoc; wayID++) {
   if (rrpv[setIndex][wayID] == 3) lrus[n++] = wayID;
  }
  if (n) {
   r = lrus[rand()%n];
  } else {
   for (unsigned int wayID=0; wayID<assoc; wayID++) rrpv[setIndex][wayID]++;
   goto startover;
  }
 } else {
  r = get_mdpp_plru_victim (setIndex);
 }
 // we now have a victim, r; predict whether this block is
 // "dead on arrival" and bypass for non-writeback accesses

 if (accessType!= WRITEBACK) {
  uint32_t tag = paddr / (llc_sets * 64);
  make_trace (tid, samp->pred, setIndex, PC, tag, accessType, false, true, lastmiss_bits[setIndex], paddr & 63);
  int prediction;
  int conf = samp->pred->get_prediction (tid, setIndex);
  if (dan_dt2) {
   if (setIndex < leaders1) 
    prediction = conf >= dan_dt1;
   else if (setIndex < leaders2)
    prediction = conf >= dan_dt2;
   else {
    if (psel >= 0)
     prediction = conf >= dan_dt2;
    else
     prediction = conf >= dan_dt1;
   }
  } else {
   prediction = conf >= dan_bypass_threshold;
  }
 
  // if block is predicted dead, then it should bypass the cache
 
  if (prediction) {
   r = LLC_WAYS; // means bypass
  }
 }

 // return the selected victim

 return r;
}


def find_victim_v2(int cpu, int set, const int * current_set, int PC, int paddr, int type) -> int:
def find_victim_v2(uint32_t cpu, uint32_t set, const int * current_set, uint64_t PC, uint64_t paddr, uint32_t type) -> uint32_t:
uint32_t find_victim_v2 (uint32_t cpu, uint32_t set, const BLOCK *current_set, uint64_t PC, uint64_t paddr, uint32_t type)
{
    if(type == 3)
        return 0;

    if(type == 2)
        return LLC_WAYS;

    if(getPCCategory(PC) == STREAMING && type!=3){
        return LLC_WAYS;
    }

    // look for the maxRRPV line
    while (1)
    {
        for (int i=0; i<LLC_WAYS; i++)
            if (rrpv[set][i] == maxRRPV){
                return i;
            }

        for (int i=0; i<LLC_WAYS; i++)
            rrpv[set][i]++;
    }

    // WE SHOULD NOT REACH HERE
    assert(0);
    return 0;

}


def find_victim_v3(int cpu, int set, const int * current_set, int PC, int paddr, int type) -> int:
def find_victim_v3(int cpu, int set, const int * current_set, int PC, int paddr, int type) -> int:
uint32_t find_victim_v3 (uint32_t cpu, uint32_t set, const BLOCK *current_set, uint64_t PC, uint64_t paddr, uint32_t type)
{
    // look for the maxRRPV line
    for (uint32_t i=0; i<LLC_WAYS; i++)
        if (rrpv[set][i] == maxRRPV)
            return i;

    //If we cannot find a cache-averse line, we evict the oldest cache-friendly line
    uint32_t max_rrip = 0;
    int32_t lru_victim = -1;
    for (uint32_t i=0; i<LLC_WAYS; i++)
    {
        if (rrpv[set][i] >= max_rrip)
        {
            max_rrip = rrpv[set][i];
            lru_victim = i;
        }
    }

    assert (lru_victim!= -1);
    //The predictor is trained negatively on LRU evictions
    if( SAMPLED_SET(set) )
    {
        if(prefetched[set][lru_victim])
            prefetch_predictor->decrement(signatures[set][lru_victim]);
        else
            demand_predictor->decrement(signatures[set][lru_victim]);
    }
    return lru_victim;

    // WE SHOULD NOT REACH HERE
    assert(0);
    return 0;
}


def find_victim_v4(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> int:
def find_victim_v4(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
long lru::find_victim_v4(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                      champsim::address full_addr, access_type type)
{
  auto begin = std::next(std::begin(last_used_cycles), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);

  // Find the way whose last use cycle is most distant
  auto victim = std::min_element(begin, end);
  assert(begin <= victim);
  assert(victim < end);
  return std::distance(begin, victim);
}


def find_victim_v5(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
{

            // Add your code here an improved cache replacement policy.
            
}

// Only write one new policy inside the function skeleton that I provided for you at the end of the code.

def find_victim_v6(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> int:
def find_victim_v6(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
long lru::find_victim_v6(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                      champsim::address full_addr, access_type type)
{
  auto begin = std::next(std::begin(last_used_cycles), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);

  // Find the way whose last use cycle is most distant
  auto victim = std::min_element(begin, end);
  assert(begin <= victim);
  assert(victim < end);
  return std::distance(begin, victim);
}


def find_victim_v7(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
def find_victim_v7(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> int:
long lru::find_victim_v7(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                      champsim::address full_addr, access_type type)
{
  auto begin = std::next(std::begin(last_used_cycles), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);

  // Find the way whose last use cycle is most distant
  auto victim = std::min_element(begin, end);
  assert(begin <= victim);
  assert(victim < end);
  return std::distance(begin, victim);
}


def find_victim_v8(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> long:
def find_victim_v8(int triggering_cpu, int instr_id, long set, const int * current_set, int ip, int full_addr, int type) -> int:
long lru::find_v


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

