{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set path = node.original_file_path -%}
    {%- if 'nba/models' in path -%}
        nba_dbt
    {%- elif 'toronto-parking/models/staging' in path -%}
        toronto_parking_dbt_staging
    {%- elif 'toronto-parking/models/intermediate' in path -%}
        toronto_parking_dbt_intermediate
    {%- elif 'toronto-parking/models/marts' in path -%}
        toronto_parking_dbt_marts
    {%- elif 'financial-due-diligence/models/bronze' in path -%}
        financial_due_diligence_bronze
    {%- elif 'financial-due-diligence/models/silver' in path -%}
        financial_due_diligence_silver
    {%- elif 'financial-due-diligence/models/gold' in path -%}
        financial_due_diligence_gold
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
