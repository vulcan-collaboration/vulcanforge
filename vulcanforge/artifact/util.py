from ming.odm import session

from vulcanforge.artifact.model import Artifact
from vulcanforge.common.util.model import build_model_inheritance_graph, dfs


def iter_artifact_classes():
    graph = build_model_inheritance_graph()
    for _, a_cls in dfs(Artifact, graph):
        if not session(a_cls):
            continue
        yield a_cls
