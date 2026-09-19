{% macro score_metric(pct_col, metric_col=None) %}
    case
        {% if metric_col is not none %}
        when {{ metric_col }} is null then null
        {% endif %}
        when {{ pct_col }} >= 0.90 then 90 + round(({{ pct_col }} - 0.90) / 0.10 * 10)
        when {{ pct_col }} >= 0.75 then 75 + round(({{ pct_col }} - 0.75) / 0.15 * 14)
        when {{ pct_col }} >= 0.50 then 50 + round(({{ pct_col }} - 0.50) / 0.25 * 24)
        when {{ pct_col }} >= 0.25 then 25 + round(({{ pct_col }} - 0.25) / 0.25 * 24)
        else round({{ pct_col }} / 0.25 * 24)
    end
{% endmacro %}
