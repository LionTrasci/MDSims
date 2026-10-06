import re
from pathlib import PurePosixPath
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Login(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class Ligand(BaseModel):
    path: str = Field(max_length=1024)
    charge: int = Field(default=0, ge=-20, le=20)
    multiplicity: int = Field(default=1, ge=1, le=10)


class Simulation(BaseModel):
    workflow: Literal["md", "mmpbsa"] = "md"
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$", default="amber-run")
    account: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    partition: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    walltime: str = Field(default="04:00:00", pattern=r"^(\d{1,2}-)?\d{1,3}:[0-5]\d:[0-5]\d$")
    run_parent: str = Field(default="", max_length=1024)
    mail_user: str = Field(default="", max_length=254, pattern=r"^$|^[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
    dependency: str = Field(default="", pattern=r"^$|^(afterok|afterany|afternotok|after):[0-9]+(:[0-9]+)*$")
    qos: str = Field(default="", pattern=r"^[A-Za-z0-9_-]{0,64}$")
    reservation: str = Field(default="", pattern=r"^[A-Za-z0-9_-]{0,64}$")
    exclusive: bool = False
    cpus: int = Field(default=1, ge=1, le=128)
    memory_gb: int = Field(default=8, ge=1, le=1024)
    engine: Literal["gpu", "cpu"] = "gpu"
    temperature: float = Field(default=298.15, ge=1, le=1000, allow_inf_nan=False)
    duration_ns: int = Field(default=100, ge=1, le=100000)
    topology: str = Field(default="", max_length=1024)
    coordinates: str = Field(default="", max_length=1024)
    protein: str = Field(default="", max_length=1024)
    ligands: list[Ligand] = Field(default_factory=list, max_length=20)
    charge_mode: Literal["explicit", "guess", "file"] = "explicit"
    gamd: bool = False
    use_conda: bool = False
    conda_sh: str = Field(default="", max_length=1024)
    conda_prefix: str = Field(default="", max_length=1024)

    @model_validator(mode="after")
    def validate_inputs(self):
        paths = self.inputs() + ([(self.run_parent, "")] if self.run_parent else [])
        if self.use_conda:
            paths += [(self.conda_sh, ""), (self.conda_prefix, "")]
            if not self.conda_sh.endswith("/conda.sh"):
                raise ValueError("Select the Conda installation's etc/profile.d/conda.sh script")
        if self.workflow == "mmpbsa" and not self.ligands:
            raise ValueError("Provide a protein PDB and at least one ligand MOL2")
        for source, _ in paths:
            p = PurePosixPath(source)
            if not source.startswith("/") or ".." in p.parts or not re.fullmatch(r"/[A-Za-z0-9_./-]+", source):
                raise ValueError("Use absolute BP1 paths with letters, numbers, /, _, - and . only")
        return self

    def inputs(self):
        if self.workflow == "md":
            return [(self.topology, "input.parm7"), (self.coordinates, "input.rst7")]
        return [(self.protein, "protein.pdb")] + [(lig.path, f"ligand{i}.mol2") for i, lig in enumerate(self.ligands, 1)]

    def check_profile(self, profile):
        if profile.get("restrict_choices", False) and (self.account not in profile["accounts"] or self.partition not in profile["partitions"]):
            raise ValueError("Account or partition is not enabled for your profile")
        root = PurePosixPath(profile["root"])
        if not root.is_absolute() or ".." in root.parts or not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(root)):
            raise ValueError("Administrator must configure an absolute, shell-safe work root")
        for source, _ in self.inputs() + ([(self.run_parent, "")] if self.run_parent else []):
            if not PurePosixPath(source).is_relative_to(root):
                raise ValueError(f"Inputs must be inside your work directory: {root}")
        days, clock = self.walltime.split("-") if "-" in self.walltime else ("0", self.walltime)
        hours, minutes, seconds = map(int, clock.split(":"))
        total = int(days) * 86400 + hours * 3600 + minutes * 60 + seconds
        if not 0 < total <= profile["max_hours"] * 3600:
            raise ValueError(f"Walltime must be positive and no more than {profile['max_hours']} hours")
        for field, limit in [("cpus", "max_cpus"), ("memory_gb", "max_memory_gb")]:
            if getattr(self, field) > profile[limit]:
                raise ValueError(f"{field} exceeds your configured limit of {profile[limit]}")
