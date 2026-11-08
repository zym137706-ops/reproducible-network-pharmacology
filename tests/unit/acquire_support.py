"""Fakes and canned responses shared by the acquire tests. Nothing here touches the network."""

from __future__ import annotations

import json

from rnp.acquire.transport import FetchResponse


def mmcif_url(pdb_id: str) -> str:
    return f"https://files.rcsb.org/download/{pdb_id}.cif"


def entry_url(pdb_id: str) -> str:
    return f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"


GRAPHQL_URL = "https://data.rcsb.org/graphql"


def uniprot_url(accession: str) -> str:
    return f"https://rest.uniprot.org/uniprotkb/{accession}.json"


def cif_body(pdb_id: str) -> bytes:
    return f"data_{pdb_id}\n#\n_entry.id   {pdb_id} \n#\n".encode()


def entry_body(pdb_id: str) -> bytes:
    return json.dumps({"entry": {"id": pdb_id}, "rcsb_id": pdb_id}).encode()


def graphql_answer(pdb_id: str) -> bytes:
    return json.dumps({"data": {"entries": [{"rcsb_id": pdb_id}]}}).encode()


def uniprot_body(accession: str) -> bytes:
    return json.dumps(
        {"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": accession}
    ).encode()


def reply(body: bytes, status: int = 200, headers: dict[str, str] | None = None) -> FetchResponse:
    return FetchResponse(status, dict(headers or {}), body)


def ok_routes(pdb_id: str, accession: str) -> dict[tuple[str, str], FetchResponse]:
    """The four successful answers for one (PDB ID, UniProt accession) pair."""
    return {
        ("GET", mmcif_url(pdb_id)): reply(cif_body(pdb_id), headers={"last-modified": "L"}),
        ("GET", entry_url(pdb_id)): reply(entry_body(pdb_id)),
        ("POST", GRAPHQL_URL): reply(graphql_answer(pdb_id)),
        ("GET", uniprot_url(accession)): reply(
            uniprot_body(accession), headers={"x-uniprot-release": "2026_04"}
        ),
    }


def ok_fetcher(pairs, extra=None):
    """A fetcher that answers every (PDB ID, UniProt accession) pair successfully. ``extra``
    routes replace or add answers; the GraphQL endpoint knows exactly the PDB IDs of ``pairs``."""
    routes = {}
    known = set()
    for pdb_id, accession in pairs:
        pair_routes = ok_routes(pdb_id, accession)
        del pair_routes[("POST", GRAPHQL_URL)]
        routes.update(pair_routes)
        known.add(pdb_id)
    routes.update(extra or {})

    def graphql(pdb_id):
        if pdb_id in known:
            return reply(graphql_answer(pdb_id))
        return reply(json.dumps({"data": {"entries": []}}).encode())

    return FakeFetcher(routes, graphql=graphql)


class FakeFetcher:
    """Answers requests from ``routes`` and records them. A GraphQL answer may be a function of
    the PDB ID in the request body. An unexpected request is a test failure (KeyError)."""

    def __init__(self, routes=None, graphql=None):
        self.routes = dict(routes or {})
        self.graphql = graphql
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        if request.method == "POST" and self.graphql is not None:
            pdb_id = json.loads(request.body)["variables"]["ids"][0]
            answer = self.graphql(pdb_id)
        else:
            answer = self.routes[(request.method, request.url)]
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def urls(self) -> list[str]:
        return [call.url for call in self.calls]


class FakeClock:
    """Returns 2026-11-08T06:00:00Z, then one second later on every further call."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> str:
        second = self.calls
        self.calls += 1
        return f"2026-11-08T06:{second // 60:02d}:{second % 60:02d}Z"
