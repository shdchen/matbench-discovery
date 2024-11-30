"""Perturb atomic coordinates of a pymatgen structure and analyze symmetry."""

import warnings

import numpy as np
import pandas as pd
import spglib
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure
from pymatviz.enums import Key
from tqdm import tqdm

from matbench_discovery.enums import MbdKey

__author__ = "Janosh Riebesell"
__date__ = "2022-12-02"

rng = np.random.default_rng(0)  # ensure reproducible structure perturbations


def perturb_structure(struct: Structure, gamma: float = 1.5) -> Structure:
    """Perturb the atomic coordinates of a pymatgen structure. Used for CGCNN+P
    training set augmentation.

    Not identical but very similar to the perturbation method used in
    https://nature.com/articles/s41524-022-00891-8#Fig5.

    Args:
        struct (Structure): pymatgen structure to be perturbed
        gamma (float, optional): Weibull distribution parameter. Defaults to 1.5.

    Returns:
        Structure: Perturbed structure
    """
    perturbed = struct.copy()
    for site in perturbed:
        magnitude = rng.weibull(gamma)
        vec = rng.normal(3)  # TODO maybe make func recursive to deal with 0-vector
        vec /= np.linalg.norm(vec)  # unit vector
        site.coords += vec * magnitude
        site.to_unit_cell(in_place=True)

    return perturbed


def analyze_symmetry(
    structures: dict[str, Structure],
    *,
    pbar: bool | dict[str, str] = True,
    symprec: float = 1e-2,
    angle_tolerance: float = -1,
) -> pd.DataFrame:
    """Analyze symmetry of a dictionary of structures using spglib.

    Args:
        structures (dict[str, Structure]): Map material IDs to pymatgen Structures
        pbar (bool | dict[str, str], optional): Whether to show progress bar.
            Defaults to True.
        symprec (float, optional): Symmetry precision of spglib.get_symmetry_dataset.
            Defaults to 1e-2.
        angle_tolerance (float, optional): Angle tol. of spglib.get_symmetry_dataset.
            Defaults to -1.

    Returns:
        pd.DataFrame: DataFrame containing symmetry information for each structure
    """
    sym_key_map = {
        "number": Key.spg_num,
        "hall_number": Key.hall_num,
        "international": MbdKey.international_spg_name,
        "hall": Key.hall_symbol,
        "choice": Key.choice_symbol,
        "pointgroup": Key.point_group,
        "wyckoffs": Key.wyckoff_symbols,
    }

    results: dict[str, dict[str, str | int | list[str]]] = {}
    iterator = structures.items()
    if pbar:
        pbar_kwargs = pbar if isinstance(pbar, dict) else {}
        iterator = tqdm(
            iterator,
            total=len(structures),
            **dict(desc="Analyzing symmetry") | pbar_kwargs,
        )

    for struct_key, struct in iterator:
        cell = (struct.lattice.matrix, struct.frac_coords, struct.atomic_numbers)
        # spglib 2.5.0 issues lots of warnings:
        # - get_bravais_exact_positions_and_lattice failed
        # - ssm_get_exact_positions failed
        with warnings.catch_warnings():
            warnings.filterwarnings(action="ignore", module="spglib")
            sym_data = spglib.get_symmetry_dataset(
                cell, symprec=symprec, angle_tolerance=angle_tolerance
            )

        if sym_data is None:
            raise ValueError(f"spglib returned None for {struct_key}\n{struct}")

        sym_info = {
            new_key: getattr(sym_data, old_key)
            for old_key, new_key in sym_key_map.items()
        } | {
            Key.n_sym_ops: len(sym_data.rotations),
            Key.n_rot_syms: len(sym_data.rotations),
            Key.n_trans_syms: len(sym_data.translations),
        }
        results[struct_key] = sym_info | dict(
            symprec=symprec, angle_tolerance=angle_tolerance
        )

    df_sym = pd.DataFrame(results).T
    df_sym.index.name = Key.mat_id
    return df_sym


def pred_vs_ref_struct_symmetry(
    df_sym_pred: pd.DataFrame,
    df_sym_ref: pd.DataFrame,
    pred_structs: dict[str, Structure],
    ref_structs: dict[str, Structure],
    *,
    pbar: bool | dict[str, str] = True,
) -> pd.DataFrame:
    """Get RMSD and compare symmetry between ML and DFT reference structures.

    Modifies the df_sym_pred DataFrame in place by adding columns for symmetry
    differences and RMSDs.

    Args:
        df_sym_pred (pd.DataFrame): symmetry information for ML model as returned by
            analyze_symmetry.
        df_sym_ref (pd.DataFrame): symmetry information for DFT reference as returned by
            analyze_symmetry.
        pred_structs (dict[str, Structure]): Map material IDs to ML-relaxed structures
        ref_structs (dict[str, Structure]): Map material IDs to reference structures
        pbar (bool | dict[str, str], optional): Whether to show progress bar.
            Defaults to True.

    Returns:
        pd.DataFrame: with added columns for symmetry differences
    """
    df_result = df_sym_pred.copy()

    # Calculate differences
    df_result[MbdKey.spg_num_diff] = df_sym_pred[Key.spg_num] - df_sym_ref[Key.spg_num]
    df_result[MbdKey.n_sym_ops_diff] = (
        df_sym_pred[Key.n_sym_ops] - df_sym_ref[Key.n_sym_ops]
    )

    structure_matcher = StructureMatcher()
    shared_ids = set(pred_structs) & set(ref_structs)

    # Initialize RMSD column
    df_result[MbdKey.structure_rmsd_vs_dft] = None

    if pbar:
        pbar_kwargs = pbar if isinstance(pbar, dict) else {}
        shared_ids = tqdm(
            shared_ids,
            **dict(leave=False, desc="Calculating RMSD") | pbar_kwargs,
        )

    for mat_id in shared_ids:
        rmsd, max_dist = structure_matcher.get_rms_dist(
            pred_structs[mat_id], ref_structs[mat_id]
        ) or (None, None)
        df_result.loc[mat_id, MbdKey.structure_rmsd_vs_dft] = rmsd
        df_result.loc[mat_id, Key.max_pair_dist] = max_dist

    return df_result
