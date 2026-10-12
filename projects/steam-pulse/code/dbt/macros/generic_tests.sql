{% test dbt_utils_free_unique_combo(model, columns) %}
-- unique combination of columns, without needing the dbt_utils package
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}

{% test avg_le_peak(model) %}
select * from {{ model }} where avg_players > peak_players + 1e-6
{% endtest %}

{% test month_not_future(model, column) %}
select * from {{ model }} where {{ column }} > date_trunc('month', current_date)
{% endtest %}

{% test in_range(model, column_name, min, max) %}
select * from {{ model }} where {{ column_name }} < {{ min }} or {{ column_name }} > {{ max }}
{% endtest %}
