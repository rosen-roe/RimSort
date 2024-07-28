from typing import List

from loguru import logger
from toposort import toposort, CircularDependencyError
import networkx as nx

from app.utils.metadata import MetadataManager
from app.views.dialogue import show_warning


def do_topo_sort(
    dependency_graph: dict[str, set[str]], active_mods_uuids: set[str]
) -> List[str]:
    """
    Sort mods using the topological sort algorithm. For each
    topological level, sort the mods alphabetically.
    """
    logger.info(f"初始化 {len(dependency_graph)} 个模组的拓扑")
    # Cache MetadataManager instance
    metadata_manager = MetadataManager.instance()
    try:
        sorted_dependencies = list(toposort(dependency_graph))
    except CircularDependencyError as e:
        find_circular_dependencies(dependency_graph)
        # Propagate the exception after handling
        raise e

    reordered = list()
    active_mods_packageid_to_uuid = dict(
        (metadata_manager.internal_local_metadata[uuid]["packageid"], uuid)
        for uuid in active_mods_uuids
    )
    for level in sorted_dependencies:
        temp_mod_set = set()
        for package_id in level:
            if package_id in active_mods_packageid_to_uuid:
                mod_uuid = active_mods_packageid_to_uuid[package_id]
                temp_mod_set.add(mod_uuid)
        # Sort packages in this topological level by name
        sorted_temp_mod_set = sorted(
            temp_mod_set,
            key=lambda uuid: metadata_manager.internal_local_metadata[uuid]["name"],
            reverse=False,
        )
        # Add into reordered set
        for sorted_mod_uuid in sorted_temp_mod_set:
            reordered.append(sorted_mod_uuid)
    logger.info(f"已完成 {len(reordered)} 个模组的拓扑排序")
    return reordered


def find_circular_dependencies(dependency_graph):
    G = nx.DiGraph(dependency_graph)
    cycles = list(nx.simple_cycles(G))

    cycle_strings = []
    if cycles:
        logger.info("检测到循环依赖关系:")
        for cycle in cycles:
            loop = " -> ".join(cycle)
            logger.info(loop)
            cycle_strings.append(loop)
    else:
        logger.info("未找到循环依赖项。")

    show_warning(
        title="无法排序",
        text="无法排序",
        information="RimSort 在您的模组列表中找到了循环依赖项。请参阅依赖项循环的详细信息。",
        details="\n\n".join(cycle_strings),
    )
