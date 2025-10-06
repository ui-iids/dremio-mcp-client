CREATE TABLE customers (
  id           serial PRIMARY KEY,
  email        text UNIQUE NOT NULL,
  full_name    text NOT NULL,
  state        varchar(2) NOT NULL,
  signup_date  date NOT NULL,
  plan         text NOT NULL
);

INSERT INTO customers (email, full_name, state, signup_date, plan) VALUES
('ada@example.com','Ada Lovelace','CA','2025-06-01','pro'),
('grace@example.com','Grace Hopper','NY','2025-06-15','free'),
('linus@example.com','Linus Torvalds','WA','2025-07-02','pro'),
('margaret@example.com','Margaret Hamilton','MA','2025-07-20','team'),
('alan@example.com','Alan Turing','CA','2025-08-05','free');
