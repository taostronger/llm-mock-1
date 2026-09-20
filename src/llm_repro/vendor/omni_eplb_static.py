# SPDX-License-Identifier: MIT
# Copyright (c) 2025-2026 Huawei Technologies Co., Ltd. All Rights Reserved.
# Extracted unchanged functions; see PROVENANCE.json and LICENSE.omni-eplb.
import numpy as np
import heapq, logging
from typing import List, Tuple, Union, Optional

def allocate_expert_deployments_improved(
    loads: Union[List[float], np.ndarray],
    expert_redundant_limit: int,
    budget_limit: int,
    load_normalization: str = None,
    is_redundant: bool = False
) -> List[int]:
    """
    Allocate expert deployments with improved strategy, supporting both rearrange-only and redundant modes.

    Args:
        loads: List or numpy array of expert loads.
        expert_redundant_limit: Maximum additional deployments per expert (total = 1 + limit).
        budget_limit: Total deployment budget.
        load_normalization: Normalization method ('log' or None).
        is_redundant: If True, allow redundant deployments; if False, each expert is deployed once.

    Returns:
        List of deployment counts for each expert.
    """
    logger = logging.getLogger(__name__)
    is_numpy = isinstance(loads, np.ndarray)
    num_experts = loads.size if is_numpy else len(loads)
    loads_list = loads.tolist() if is_numpy else list(loads)
    
    if load_normalization == 'log':
        normalized_loads = [np.log1p(load) for load in loads_list]
    else:
        normalized_loads = loads_list

    deployments = [1] * num_experts
    if not is_redundant:
        return deployments  # Rearrange-only mode: each expert deployed once

    # Redundant mode: allow multiple deployments
    remaining_budget = budget_limit
    max_deployments_per_expert = 1 + expert_redundant_limit

    if remaining_budget == 0:
        return deployments

    heap = []
    for i in range(num_experts):
        original_load = normalized_loads[i]
        current_deploy_count = deployments[i]
        priority = -original_load / current_deploy_count if original_load > 0 else 0.0
        if current_deploy_count < max_deployments_per_expert:
            heap.append((priority, original_load, i))
    heapq.heapify(heap)

    deployments_added = 0
    while deployments_added < remaining_budget and heap:
        neg_load_per_instance, original_load, index = heapq.heappop(heap)
        deployments[index] += 1
        deployments_added += 1
        new_deploy_count = deployments[index]

        if new_deploy_count < max_deployments_per_expert:
            new_priority = -original_load / new_deploy_count if original_load > 0 else 0.0
            heapq.heappush(heap, (new_priority, original_load, index))

    if deployments_added < remaining_budget:
        logger.warning(f"Allocated {deployments_added} / {remaining_budget} of the budget.")
    
    return deployments

def distribute_experts_to_ranks(
    initial_loads: Union[List[float], np.ndarray],
    deployments: List[int],
    num_ranks_target_pattern: int,
    layer_idx: int = 0
) -> Tuple[float, np.ndarray]:
    """
    Distribute experts to ranks based on loads and deployments.

    Args:
        initial_loads: List or numpy array of initial expert loads.
        deployments: List of deployment counts for each expert.
        num_ranks_target_pattern: Number of target ranks.

    Returns:
        Tuple of maximum device load and placement matrix.
    """
    logger = logging.getLogger(__name__)
    if isinstance(initial_loads, list):
        loads_np = np.array(initial_loads, dtype=float)
    elif isinstance(initial_loads, np.ndarray):
        if initial_loads.ndim != 1:
            raise ValueError("Input initial_loads must be one-dimensional.")
        loads_np = initial_loads.astype(float)
    else:
        raise TypeError("initial_loads must be a list or numpy.ndarray.")

    if not isinstance(deployments, list) or not all(isinstance(d, int) for d in deployments):
        raise TypeError("deployments must be a list of integers.")
    if len(loads_np) != len(deployments):
        raise ValueError("initial_loads and deployments must have the same length.")
    if num_ranks_target_pattern <= 0:
        raise ValueError("num_ranks_target_pattern must be a positive integer.")

    num_experts = len(loads_np)
    total_deployments = sum(deployments)
    if total_deployments == 0:
        return 0.0, np.zeros((num_ranks_target_pattern, num_experts), dtype=int)

    if total_deployments % num_ranks_target_pattern != 0:
        raise ValueError(
            f"Total deployments ({total_deployments}) must be divisible by target rank count "
            f"({num_ranks_target_pattern})."
        )

    experts_per_rank = total_deployments // num_ranks_target_pattern
    if experts_per_rank == 0 and total_deployments > 0:
        raise ValueError("Calculated experts per rank is 0, but total deployments is greater than 0.")

    if experts_per_rank > num_experts:
        raise ValueError(
            f"Each rank requires ({experts_per_rank}) expert instances, "
            f"but only ({num_experts}) unique expert types are available."
        )

    max_deployments = max(deployments)
    if max_deployments > num_ranks_target_pattern:
        max_req_expert_idx = np.argmax(deployments)
        raise ValueError(f"Expert {max_req_expert_idx} requires {deployments[max_req_expert_idx]} deployments, "
                         f"exceeding the total number of target ranks {num_ranks_target_pattern}.")

    expert_instances = []
    for expert_idx, count in enumerate(deployments):
        if count > 0:
            load = loads_np[expert_idx] / count
            for _ in range(count):
                expert_instances.append((load, expert_idx))

    expert_instances.sort(key=lambda x: x[0], reverse=True)

    device_loads = np.zeros(num_ranks_target_pattern, dtype=float)
    placement_matrix = np.zeros((num_ranks_target_pattern, num_experts), dtype=int)
    device_expert_counts = np.zeros(num_ranks_target_pattern, dtype=int)
    
    start_rank = 0
    logger.info(f"Layer {layer_idx}: Starting expert placement from rank {start_rank}")

    for load, expert_idx in expert_instances:
        best_device = -1
        min_load_for_candidate = float('inf')

        possible_devices = []
        for i in range(num_ranks_target_pattern):
            rank_id = (start_rank + i) % num_ranks_target_pattern
            can_place_expert = (placement_matrix[rank_id, expert_idx] == 0)
            has_space = (device_expert_counts[rank_id] < experts_per_rank)
            if can_place_expert and has_space:
                possible_devices.append(rank_id)

        if not possible_devices:
            raise RuntimeError(f"Unable to find a suitable rank for expert {expert_idx} (load {load}).")

        best_device = possible_devices[0]
        for i in range(1, len(possible_devices)):
            if (device_loads[possible_devices[i]] < device_loads[best_device]):
                best_device = possible_devices[i]

        placement_matrix[best_device, expert_idx] = 1
        device_loads[best_device] += load
        device_expert_counts[best_device] += 1

    new_placement_matrix = placement_matrix.copy()
    num_ranks_per_host = 16
    num_hosts = max(int((num_ranks_target_pattern + 1) / num_ranks_per_host), 1)
    host_cur_rank = [0] * num_hosts
    for i in range(num_ranks_target_pattern):
        new_host_id = i % num_hosts
        new_placement_matrix[new_host_id * num_ranks_per_host + host_cur_rank[new_host_id]] = placement_matrix[i]
        host_cur_rank[new_host_id] += 1
    placement_matrix = new_placement_matrix
    if not np.all(device_expert_counts == experts_per_rank):
        logger.warning(
            f"Expert counts per rank after allocation do not all equal the expected value {experts_per_rank}.")
        logger.warning(f"Actual counts: {device_expert_counts}")

    max_device_load = np.max(device_loads) if total_deployments > 0 else 0.0
    return max_device_load, placement_matrix
