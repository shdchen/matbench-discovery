# %%
from pymatviz import density_scatter

from matbench_discovery.enums import MbdKey, Model
from matbench_discovery.preds import df_preds

__author__ = "Janosh Riebesell"
__date__ = "2024-02-03"


# %%
df_preds[Model.gnome].hist(bins=100, figsize=(10, 10))


# %%
density_scatter(df=df_preds, x=MbdKey.e_form, y=Model.gnome)
