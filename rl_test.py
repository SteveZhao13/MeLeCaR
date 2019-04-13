import argparse
import gym
import numpy as np
import torch
import os
import gc

from config import *
import rl_envs
from utils.parser_util import str2bool

# @profile
def run(state, model, hidden_state, num_feature, prev_timestep, env, starting_request):
  state = torch.from_numpy(state.reshape(1, 1, num_feature)).float().to(DEVICE)

  with torch.no_grad():
    dist, _, hidden_state = model(state, hidden_state)

  action = dist.sample().cpu().numpy()[0]
  state, _, done, info = env.step(action)
  
  if info["timestep"] - prev_timestep >= 100000:
    print("Current timestep: {}\tHit: {}\tHitrate: {}".format(info["timestep"], info["hit"], info["hit"]/(info["timestep"] - starting_request)))
    prev_timestep = info["timestep"]
    gc.collect()

  return state, done, hidden_state, prev_timestep, info

def test(num_tests, task_name, file_index, num_actions, starting_request, max_requests, input_dir, input_model):
  assert task_name in TASKS, "Invalid task. Choices: {}".format(TASKS)
  assert file_index in FILE_INDEX, "Invalid file index. Choices: {}".format(FILE_INDEX)
  assert num_actions in CACHE_SIZE, "Invalid number of actions. Choices: {}".format(CACHE_SIZE)
  assert max_requests in MAX_REQUESTS, "Invalid maximum requests allowed. Choices: {}".format(MAX_REQUESTS)
  assert os.path.isdir(input_dir), "Input directory {} doesn't exist".format(input_dir)

  model_full_path = input_dir.rstrip("/") + "/" + input_model

  assert os.path.isfile(model_full_path), "Input model {} doesn't exist".format(model_full_path)

  num_feature = num_actions * 3

  # Setup environment

  task_name = "Cache-Bandit-C{}-Max{}-{}-{}-v0".format(num_actions, max_requests, task_name, file_index)

  env = gym.make(task_name)

  # Create the model
  model = torch.load(model_full_path, map_location=MAP_LOCATION)
  model.eval()

  print("Test task: {}".format(task_name))
  print("Input model: {}".format(model_full_path))
  print("Starting request: {}".format(starting_request))

  hit_rates = []
  for i in range(num_tests):
    print("Performing test {} ==========================================".format(i))
    state = env.reset(starting_request)
    done = False
    hidden_state = model.init_hidden_state(1).to(DEVICE)
    prev_timestep = 0
    result = None

    while not done:
      state, done, hidden_state, prev_timestep, result = run(state, model, hidden_state, num_feature, prev_timestep, env, starting_request)

    print("All requests are processed - Number of hits: {}\tNumber of requests: {}\tHit Ratio: {}".format(result["hit"], result["timestep"] - result["starting_request"], result["hit"]/(result["timestep"] - result["starting_request"])))

    hit_rates.append(result["hit"]/(result["timestep"] - result["starting_request"]))

  hit_rates = np.array(hit_rates)
  print("Average: {}\tStandard Deviation: {}".format(np.average(hit_rates), np.std(hit_rates)))


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--num_tests', type=int, default=10, help='number of tests to perform')

  parser.add_argument("--task_name", type=str, help="the task to learn", default="home", choices=TASKS)
  parser.add_argument("--file_index", type=int, help="the blocktrace file index", default=6, choices=FILE_INDEX)
  parser.add_argument("--num_actions", type=int, help="the number of actions in the task", default=30, choices=CACHE_SIZE)
  parser.add_argument("--max_requests", type=int, help="the maximum number of requests from workload", default=50000, choices=MAX_REQUESTS)
  parser.add_argument("--starting_request", type=int, help="the starting request from workload", default=10000)

  parser.add_argument("--input_dir", type=str, help="the directory to load the models from", required=True)
  parser.add_argument("--input_model", type=str, help="the model to load", required=True)

  args = parser.parse_args()

  test(args.num_tests, args.task_name, args.file_index, args.num_actions, args.starting_request, args.max_requests, args.input_dir, args.input_model)
