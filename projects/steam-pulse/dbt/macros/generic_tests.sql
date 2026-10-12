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
