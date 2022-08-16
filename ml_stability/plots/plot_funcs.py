# %%
from typing import Literal

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.offsetbox import AnchoredText


__author__ = "Janosh Riebesell"
__date__ = "2022-08-05"

"""
Histogram of the energy difference (either according to DFT ground truth [default] or
model predicted energy) to the convex hull for materials in the WBM data set. The
histogram is broken down into true positives, false negatives, false positives, and true
negatives based on whether the model predicts candidates to be below the known convex
hull. Ideally, in discovery setting a model should exhibit high recall, i.e. the
majority of materials below the convex hull being correctly identified by the model.

See fig. S1 in https://science.org/doi/10.1126/sciadv.abn4117.
"""


plt.rc("savefig", bbox="tight", dpi=200)
plt.rcParams["figure.constrained_layout.use"] = True
plt.rc("figure", dpi=150)
plt.rc("font", size=14)


def hist_classify_stable_as_func_of_hull_dist(
    # df: pd.DataFrame,
    formation_energy_targets: pd.Series,
    formation_energy_preds: pd.Series,
    e_above_hull_vals: pd.Series,
    rare: str = "all",
    std_vals: pd.Series = None,
    criterion: Literal["energy", "std", "neg"] = "energy",
    energy_type: Literal["true", "pred"] = "true",
    annotate_all_stats: bool = False,
) -> plt.Axes:
    """
    Histogram of the energy difference (either according to DFT ground truth [default]
    or model predicted energy) to the convex hull for materials in the WBM data set. The
    histogram is broken down into true positives, false negatives, false positives, and
    true negatives based on whether the model predicts candidates to be below the known
    convex hull. Ideally, in discovery setting a model should exhibit high recall, i.e.
    the majority of materials below the convex hull being correctly identified by the
    model.

    See fig. S1 in https://science.org/doi/10.1126/sciadv.abn4117.


    # NOTE this figure plots hist bars separately which causes aliasing in pdf
    # to resolve this take into Inkscape and merge regions by color
    """
    assert e_above_hull_vals.isna().sum() == 0

    error = formation_energy_preds - formation_energy_targets
    mean = error + e_above_hull_vals

    test = mean

    if std_vals is not None:
        if criterion == "std":
            test += std_vals
        elif criterion == "neg":
            test -= std_vals

    xlim = (-0.4, 0.4)

    # set stability threshold at on or 0.1 eV / atom above the hull
    stability_thresh = (0, 0.1)[0]

    actual_pos = e_above_hull_vals <= stability_thresh
    actual_neg = e_above_hull_vals > stability_thresh
    model_pos = test <= stability_thresh
    model_neg = test > stability_thresh

    n_true_pos = len(e_above_hull_vals[actual_pos & model_pos])
    n_false_neg = len(e_above_hull_vals[actual_pos & model_neg])

    n_total_pos = n_true_pos + n_false_neg

    # --- histogram by DFT-computed distance to convex hull
    if energy_type == "true":
        true_pos = e_above_hull_vals[actual_pos & model_pos]
        false_neg = e_above_hull_vals[actual_pos & model_neg]
        false_pos = e_above_hull_vals[actual_neg & model_pos]
        true_neg = e_above_hull_vals[actual_neg & model_neg]
        xlabel = r"$\Delta E_{Hull-MP}$ / eV per atom"

    # --- histogram by model-predicted distance to convex hull
    if energy_type == "pred":
        true_pos = mean[actual_pos & model_pos]
        false_neg = mean[actual_pos & model_neg]
        false_pos = mean[actual_neg & model_pos]
        true_neg = mean[actual_neg & model_neg]
        xlabel = r"$\Delta E_{Hull-Pred}$ / eV per atom"

    fig, ax = plt.subplots(1, 1, figsize=(10, 9))

    ax.hist(
        [true_pos, false_neg, false_pos, true_neg],
        bins=200,
        range=xlim,
        alpha=0.5,
        color=["tab:green", "tab:orange", "tab:red", "tab:blue"],
        label=[
            "True Positives",
            "False Negatives",
            "False Positives",
            "True Negatives",
        ],
        stacked=True,
    )

    ax.legend(frameon=False, loc="upper left")

    n_true_pos, n_false_pos, n_true_neg, n_false_neg = (
        len(true_pos),
        len(false_pos),
        len(true_neg),
        len(false_neg),
    )
    # null = (tp + fn) / (tp + tn + fp + fn)
    Null = n_total_pos / len(e_above_hull_vals)
    PPV = n_true_pos / (n_true_pos + n_false_pos)
    TPR = n_true_pos / n_total_pos
    F1 = 2 * PPV * TPR / (PPV + TPR)

    assert n_true_pos + n_false_pos + n_true_neg + n_false_neg == len(
        formation_energy_targets
    )

    RMSE = (error**2.0).mean() ** 0.5
    MAE = error.abs().mean()

    # anno_text = f"Prevalence = {null:.2f}\nPrecision = {ppv:.2f}\nRecall = {tpr:.2f}",
    anno_text = f"Enrichment Factor = {PPV/Null:.3}"
    if annotate_all_stats:
        anno_text += f"\n{MAE = :.3}\n{RMSE = :.3}\n{Null = :.3}\n{TPR = :.3}"
    else:
        print(f"{PPV = :.3}")
        print(f"{TPR = :.3}")
        print(f"{F1 = :.3}")
        print(f"Enrich: {PPV/Null:.2f}")
        print(f"{Null = :.3}")
        print(f"{MAE = :.3}")
        print(f"{RMSE = :.3}")

    text_box = AnchoredText(
        anno_text, loc="upper right", frameon=False, prop=dict(fontsize=16)
    )
    ax.add_artist(text_box)

    ax.set(
        xlabel=xlabel,
        ylabel="Number of Compounds",
        title=f"data size = {len(e_above_hull_vals):,}",
    )

    return ax
