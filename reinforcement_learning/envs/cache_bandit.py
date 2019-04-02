import numpy as np
import pandas as pd
from sklearn.preprocessing import normalize
from collections import defaultdict

import gym
from gym import spaces

location_prefix = "envs/"

class CacheBandit(gym.Env):
  def __init__(self, cache_size, workload, max_len):
    self.cache_size = cache_size
    self.workload = location_prefix + workload

    self.action_space = spaces.Discrete(self.cache_size)
    self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(self.cache_size, 3))

    self._next_evict_time = 0
    df = pd.read_csv(self.workload, sep=' ',header = None)
    df.columns = ['timestamp','pid','pname','blockNo', \
                  'blockSize', 'readOrWrite', 'bdMajor', 'bdMinor', 'hash']

    self._stream = df['blockNo'].tolist()[450:550]
    self._size = len(self._stream)
    self._counter = 0

    self._lfu = defaultdict(int)
    self._lru = []
    self._cache = []

    self._fill_until_evict()


  def _compute_state(self):
    recency = []
    frequency = []
    recency_dict = defaultdict(int)
    
    # Compute the recency order of each page in cache
    for time in range(len(self._lru)):
      recency_dict[self._lru[time]] = time + 1
    for block in self._cache:
      recency.append(recency_dict[block])
      frequency.append(self._lfu[block])

    block_num = self._cache[:]
    
    if len(recency) < self.cache_size:
        for i in range(0, self.cache_size - len(recency)):
            recency.append(0)
            frequency.append(0)
            block_num.append(0)
    
    # Columns: recency, frequency, block number
    # Row: cache location
    raw_input = np.column_stack((recency, frequency, block_num))
    
    return raw_input#normalize(raw_input, axis=0)


  def _fill_until_evict(self):
    needs_evict = False
    while not needs_evict and self._counter < self._size:
      request_block = self._stream[self._counter]
      self._lfu[request_block] += 1

      if request_block in self._cache:
        self._lru.remove(request_block)
        self._lru.append(request_block)
        self._counter += 1
      else:
        if len(self._cache) == self.cache_size:
          needs_evict = True
          # self._next_evict_time = self._counter
        else:
          self._cache.append(request_block)
          self._lru.append(request_block)
          self._counter += 1
    

  def reset(self):
    self._next_evict_time = 0
    self._counter = 0
    self._lfu = defaultdict(int)
    self._lru = []
    self._cache = []
    self._fill_until_evict()
    return self._compute_state()


  def step(self, action):
    assert self.action_space.contains(action)

    victim_block = self._cache[action]
    request_block = self._stream[self._counter]
    
    self._lru.remove(victim_block)
    self._lfu[victim_block] = 0
    self._cache.remove(victim_block)

    # Insert the page
    self._cache.append(request_block)
    self._lru.append(request_block)
    self._lfu[request_block] = 1
    self._counter += 1
    curr_timestep = self._counter
    
    self._fill_until_evict()
    return self._compute_state(), (self._counter - curr_timestep), self._counter == self._size, {"workload": self.workload, "timestep": self._counter, "curr": curr_timestep}
