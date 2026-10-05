"""Exercise orchestration with mocked Amber bindings; no molecular computation."""
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import Mock
import pytest

SOURCE = Path(__file__).resolve().parents[3] / "AmberMDrun"


def load_wrapper(monkeypatch, name):
    package = types.ModuleType("wrapper_test")
    package.__path__ = [str(SOURCE)]
    pyamber = types.ModuleType("wrapper_test.pyamber")
    pyamber.SystemInfo = Mock()
    pyamber.NPT = Mock()
    pyamber.GaMd = Mock()
    equil = types.ModuleType("wrapper_test.equil")
    equil.prep = Mock(return_value="prepared.rst7")
    monkeypatch.setitem(sys.modules, "wrapper_test", package)
    monkeypatch.setitem(sys.modules, "wrapper_test.pyamber", pyamber)
    monkeypatch.setitem(sys.modules, "wrapper_test.equil", equil)
    spec = importlib.util.spec_from_file_location(f"wrapper_test.{name}", SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, pyamber


def test_analysis_honors_slurm(monkeypatch):
    module, _ = load_wrapper(monkeypatch, "mmpbsa")
    monkeypatch.delenv("MDSIMS_MPI_RANKS", raising=False)
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "3")
    assert module.analysis_ranks() == 3
    monkeypatch.setenv("MDSIMS_MPI_RANKS", "4")
    assert module.analysis_ranks() == 4
    monkeypatch.setenv("MDSIMS_MPI_RANKS", "0")
    with pytest.raises(ValueError): module.analysis_ranks()


def test_charge_arguments_use_correct_keywords(monkeypatch):
    module, _ = load_wrapper(monkeypatch, "mmpbsa")
    args = types.SimpleNamespace(protein="p.pdb", mol2=["a.mol2", "b.mol2"], temp=301,
        guess_charge=False, user_charge=False, charge=[0, -1], multiplicity=[1, 2], MIN="sander", MD="sander", ns=1)
    module.arg_parse = lambda: args
    # Stop at tleap; inspect the actual wrapper call before expensive work.
    module.run_tleap = Mock(side_effect=RuntimeError("stop"))
    with pytest.raises(RuntimeError, match="stop"): module.mmpbsa()
    module.run_tleap.assert_called_once_with("p.pdb", args.mol2, user_charge=False,
        charge=[0, -1], multiplicity=[1, 2], guess_charge=False)
    args.multiplicity = [1]
    with pytest.raises(ValueError, match="one charge"): module.mmpbsa()


def test_automatic_ligand_split_precedes_charge_validation(monkeypatch):
    module, _ = load_wrapper(monkeypatch, "mmpbsa")
    module.arg_parse = lambda: types.SimpleNamespace(protein="complex.pdb", mol2=None, temp=300,
        guess_charge=False, user_charge=False, charge=[0], multiplicity=[1])
    module.split_pdb = Mock(return_value=("p.pdb", "lig.mol2"))
    module.run_tleap = Mock(side_effect=RuntimeError("stop"))
    with pytest.raises(RuntimeError, match="stop"): module.mmpbsa()
    module.split_pdb.assert_called_once()


@pytest.mark.parametrize("gamd", [False, True])
def test_production_temperature_is_preserved(monkeypatch, gamd):
    module, bindings = load_wrapper(monkeypatch, "main")
    system = bindings.SystemInfo.return_value
    system.getHeavyMask.return_value = ":1"
    system.getBackBoneMask.return_value = "@CA"
    module.arg_parse = lambda: types.SimpleNamespace(parm7="input.parm7", rst7="input.rst7", temp=315,
        gamd=gamd, MIN="sander", MD="sander", ns=1, addmask=None)
    module.main()
    engine = bindings.GaMd if gamd else bindings.NPT
    assert engine.call_args.kwargs["temp"] == 315
