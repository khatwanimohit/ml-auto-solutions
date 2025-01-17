# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities to construct job sweep GKE configs for maxtext DAG."""

from xlml.apis import gcp_config, metric_config, task, test_config
from dags.vm_resource import TpuVersion
import itertools
from typing import List, Iterable, Dict, Any


def get_maxtext_sweep_gke_config(
    test_owner: str,
    tpu_version: TpuVersion,
    num_slices: List[int],
    sweep_params: Dict[str, List[Any]],
    tpu_cores: int,
    tpu_zone: str,
    time_out_in_min: int,
    run_name_prefix: str,
    project_name: str,
    cluster_name: str,
    docker_image: str,
    base_output_directory: str,
    base_run_model_cmds: Iterable[str],
    base_set_up_cmds: Iterable[str] = None,
    dataset_name: metric_config.DatasetOption = metric_config.DatasetOption.BENCHMARK_DATASET,
    metric_aggregation_strategy: metric_config.AggregationStrategy = metric_config.AggregationStrategy.MEDIAN,
) -> List[task.TpuXpkTask]:
  job_gcp_config = gcp_config.GCPConfig(
      project_name=project_name,
      zone=tpu_zone,
      dataset_name=dataset_name,
      dataset_project=project_name,
      composer_project=project_name,
  )

  # Add num_slices as a sweep param
  sweep_params["NUM_SLICES"] = num_slices

  # Convert sweep_params to a list of lists to generate sweep param combinations
  sweep_params_list = []
  for param, values in sweep_params.items():
    sweep_params_list.append([(param, val) for val in values])

  # Generate all combinations of sweep param configurations and create a TpuXpkTask for each one
  xpk_task_list = []
  for idx, config in enumerate(itertools.product(*sweep_params_list)):
    config_dict = {key: value for (key, value) in config}

    # Remove num_slices as a sweep param after combinations have been generated
    curr_num_slices = config_dict["NUM_SLICES"]
    del config_dict["NUM_SLICES"]

    # Export sweep params as env variables for MaxText to read
    run_model_cmds = [f"export {key}={value}" for (key, value) in config_dict.items()]
    for cmd in base_run_model_cmds:
      run_model_cmds.append(cmd)

    job_test_config = test_config.TpuGkeTest(
        test_config.Tpu(
            version=tpu_version,
            cores=tpu_cores,
        ),
        test_name=f"{run_name_prefix}-{idx}",
        set_up_cmds=base_set_up_cmds,
        run_model_cmds=run_model_cmds,
        time_out_in_min=time_out_in_min,
        task_owner=test_owner,
        num_slices=curr_num_slices,
        cluster_name=cluster_name,
        docker_image=docker_image,
    )

    job_metric_config = metric_config.MetricConfig(
        tensorboard_summary=metric_config.SummaryConfig(
            file_location=base_output_directory,
            aggregation_strategy=metric_aggregation_strategy,
            use_regex_file_location=True,
        ),
    )

    xpk_task = task.TpuXpkTask(
        task_test_config=job_test_config,
        task_gcp_config=job_gcp_config,
        task_metric_config=job_metric_config,
    )
    xpk_task_list.append(xpk_task)

  return xpk_task_list
