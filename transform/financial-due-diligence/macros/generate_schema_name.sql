{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set path = node.original_file_path -%}
    {%- if 'seeds' in path -%}
        financial_due_diligence_bronze
    {%- elif 'models/bronze' in path -%}
        financial_due_diligence_bronze
    {%- elif 'models/silver' in path -%}
        financial_due_diligence_silver
    {%- elif 'models/gold' in path -%}
        financial_due_diligence_gold
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
