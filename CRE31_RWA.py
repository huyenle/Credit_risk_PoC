# Defaulted exposure for RWA calculation
# for defaulted exposure, the capital requirement is equal to the difference between the LGD and the bank expected loss:
# not using vasicek formula as for the performing loans since PD = 1.


# Performing loans are calculated using the Vasicek formula,
# which takes into account the probability of default (PD), loss given default (LGD), and exposure at default (EAD).
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.pyplot import plot, scatter
from scipy.stats import norm

# CRE31 PD floor: 0.05% for corporate, sovereign and bank exposures.
PD_FLOOR = 0.0005

# Basel multiplier to convert a capital requirement (K) into a risk weight.
# RW = K * 12.5 (i.e. 1 / 8% minimum capital ratio). The old 1.06 scaling
# factor was removed in the finalised Basel III framework, so it is not applied.
RW_MULTIPLIER = 12.5


def corporate_sovereign_correlation(pd):
    """
    Calculate the asset correlation (R) for corporate and sovereign exposures
    based on the probability of default (PD), per the CRE31 IRB formula.

    Parameters:
    pd (float): Probability of default (between 0 and 1).

    Returns:
    float: Asset correlation.
    """
    lower_weight = (1 - np.exp(-50 * pd)) / (1 - np.exp(-50))
    return 0.12 * lower_weight + 0.24 * (1 - lower_weight)


def simulate_corporate_sovereign_correlation(num_simulations=10000):
    """
    Simulate asset correlation using Monte Carlo simulation.

    Parameters:
    num_simulations (int): Number of simulations to run.

    Returns:
    float: Simulated asset correlation.
    """
    correlations = []
    pd = np.random.uniform(
        0, 1, num_simulations
    )  # Simulate PDs uniformly between 0 and 1
    for i in range(num_simulations):
        # Simulate a random variable from a normal distribution
        # pd = np.random.uniform(0, 1)
        # Calculate the asset correlation based on the PD
        corr = corporate_sovereign_correlation(pd[i])
        correlations.append(corr)

    #    plot the distribution of simulated asset correlations
    scatter(pd, correlations)
    plt.title("Simulated Asset Correlation Distribution")
    plt.xlabel("pd")
    plt.ylabel("asset correlation")
    plt.show()

    return np.mean(correlations)


def maturity_adjustment(maturity, pd):
    """
    Calculate maturity adjustment based on the maturity of the exposure.
    """
    b = (0.11852 - 0.05478 * np.log(pd)) ** 2
    return 1 / (1 - 1.5 * b) + (maturity - 2.5) * b / (1 - 1.5 * b)


def simulate_maturity_adjustment(num_simulations=10000):
    """
    Simulate maturity adjustment using Monte Carlo simulation.

    Parameters:
    num_simulations (int): Number of simulations to run.

    Returns:
    float: Simulated maturity adjustment.
    """
    adjustments = {}
    pds = [0.02, 0.2, 0.5, 0.9, 1.0]  # Simulate PDs uniformly between 0 and 1
    maturity = np.random.uniform(
        1, 10, num_simulations
    )  # Simulate maturities between 1 and 10 years
    for pd in pds:
        adjustments[pd] = []
        for i in range(num_simulations):
            # Calculate the maturity adjustment based on the PD and maturity
            adj = maturity_adjustment(maturity[i], pd)
            adjustments[pd].append(adj)
    for pd in pds:
        scatter(
            maturity,
            adjustments[pd],
            label=f"PD={pd}. Mean MA ={np.mean(adjustments[pd]):.4f}",
            s=1,
        )

    plt.axvline(x=2.5, color="r", linestyle="--", label="Maturity = 2.5 years baseline")
    plt.title("Simulated Maturity Adjustment Distribution")
    plt.xlabel("Maturity (years)")
    plt.ylabel("Maturity Adjustment")
    plt.annotate(
        "no adjustment at maturity = 1",
        xy=(1, 1),
        xytext=(1.6, 1.5),
        arrowprops=dict(facecolor="black", shrink=0.01, width=0.5, headwidth=5),
    )
    plt.legend()
    plt.show()
    return adjustments


def capital_requirement_rate_defaulted_exposure(lgd_downturn, expected_loss):
    """
    Calculate capital requirement for defaulted exposure.
    """
    return max(0, lgd_downturn - expected_loss)


def capital_requirement_rate_performing_exposure(pd, lgd, maturity):
    """
    Calculate capital requirement (K) for performing exposure using the Vasicek formula.

    The PD is floored at PD_FLOOR (0.05%) per CRE31 before entering the formula.
    """
    pd = max(pd, PD_FLOOR)

    corr = corporate_sovereign_correlation(pd)
    ma = maturity_adjustment(maturity, pd)

    # Conditional (worst-case) default rate at the 99.9% confidence level.
    conditional_pd = norm.cdf(
        norm.ppf(pd) * np.sqrt(1 / (1 - corr))
        + norm.ppf(0.999) * np.sqrt(corr / (1 - corr))
    )

    k = lgd * (conditional_pd - pd) * ma

    return k


def risk_weight(k):
    """
    Convert a capital requirement rate (K) into a risk weight: RW = K * 12.5.
    """
    return k * RW_MULTIPLIER


def rwa(k, ead):
    """
    Calculate risk-weighted assets: RWA = K * 12.5 * EAD.

    Parameters:
    k (float): Capital requirement rate from the performing/defaulted functions.
    ead (float): Exposure at default (currency amount).

    Returns:
    float: Risk-weighted assets.
    """
    return risk_weight(k) * ead


if __name__ == "__main__":
    # Example usage
    # pd_example = 0.02  # Example probability of default
    # corr_example = corporate_sovereign_correlation(pd_example)
    # print(f"Asset correlation for PD={pd_example}: {corr_example:.4f}")

    # Simulate asset correlation
    # mean_corr = simulate_corporate_sovereign_correlation(num_simulations=10000)
    # print(f"Mean simulated asset correlation: {mean_corr:.4f}")

    # Simulate maturity adjustment
    # ma = simulate_maturity_adjustment(num_simulations=10000)

    # Performing exposure end-to-end: K -> RW -> RWA
    pd, lgd, maturity, ead = 0.02, 0.45, 2.5, 1_000_000
    k = capital_requirement_rate_performing_exposure(pd, lgd, maturity)
    print(f"Performing (PD={pd}, LGD={lgd}, M={maturity}):")
    print(f"  K   = {k:.4%}")
    print(f"  RW  = {risk_weight(k):.4%}")
    print(f"  RWA = {rwa(k, ead):,.2f}")

    # Defaulted exposure: K = max(0, LGD_downturn - EL_best_estimate)
    k_def = capital_requirement_rate_defaulted_exposure(
        lgd_downturn=0.60, expected_loss=0.45
    )
    print(f"Defaulted (LGD_downturn={0.60:.4%}, EL={0.45:.4%}):")
    print(f"  K   = {k_def:.4%}")
    print(f"  RWA = {rwa(k_def, ead):,.2f}")

    # At pd floor, even when PD is below the floor, the capital requirement should be calculated using the floor value.
    pd_floor_example = 0.0001  # Below the PD floor
    k_floor = capital_requirement_rate_performing_exposure(
        pd_floor_example, lgd, maturity
    )
    print(f"Performing (PD={pd_floor_example}, LGD={lgd}, M={maturity}):")
    print(f"  K   = {k_floor:.4%}")
    print(f"  RW  = {risk_weight(k_floor):.4%}")
    print(f"Performing (PD={PD_FLOOR}, LGD={lgd}, M={maturity}):")
    k = capital_requirement_rate_performing_exposure(PD_FLOOR, lgd, maturity)
    print(f"  K   = {k:.4%}")
    print(f"  RW  = {risk_weight(k):.4%}")
