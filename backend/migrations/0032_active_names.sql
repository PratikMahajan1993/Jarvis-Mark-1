-- Description: keep original labels on superseded master-data rows
-- Dependencies: 0004, 0006, 0024, 0030

ALTER TABLE customers ADD COLUMN recorded_name TEXT;
ALTER TABLE suppliers ADD COLUMN recorded_name TEXT;
ALTER TABLE outsource_vendors ADD COLUMN recorded_name TEXT;
ALTER TABLE materials ADD COLUMN recorded_grade TEXT;
ALTER TABLE products ADD COLUMN recorded_product_number TEXT;

UPDATE customers
SET recorded_name = substr(name, 1, instr(name, ' [superseded ') - 1)
WHERE recorded_name IS NULL
  AND instr(name, ' [superseded ') > 1;

UPDATE suppliers
SET recorded_name = substr(name, 1, instr(name, ' [superseded ') - 1)
WHERE recorded_name IS NULL
  AND instr(name, ' [superseded ') > 1;

UPDATE outsource_vendors
SET recorded_name = substr(name, 1, instr(name, ' [superseded ') - 1)
WHERE recorded_name IS NULL
  AND instr(name, ' [superseded ') > 1;

UPDATE materials
SET recorded_grade = substr(grade, 1, instr(grade, ' [superseded ') - 1)
WHERE recorded_grade IS NULL
  AND instr(grade, ' [superseded ') > 1;

UPDATE products
SET recorded_product_number = substr(product_number, 1, instr(product_number, ' [superseded ') - 1)
WHERE recorded_product_number IS NULL
  AND instr(product_number, ' [superseded ') > 1;
