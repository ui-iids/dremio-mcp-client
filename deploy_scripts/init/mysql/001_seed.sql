CREATE TABLE invoices (
  id              bigint PRIMARY KEY AUTO_INCREMENT,
  customer_email  varchar(255) NOT NULL,
  amount_cents    int NOT NULL,
  status          enum('pending','paid','failed') NOT NULL,
  paid_at         datetime NULL
);

INSERT INTO invoices (customer_email, amount_cents, status, paid_at) VALUES
('ada@example.com',     1999, 'paid',   '2025-08-01 10:00:00'),
('ada@example.com',     2999, 'paid',   '2025-08-20 09:30:00'),
('grace@example.com',    999, 'failed', NULL),
('linus@example.com',   4999, 'paid',   '2025-09-01 12:00:00'),
('margaret@example.com',7999, 'pending',NULL),
('alan@example.com',     999, 'paid',   '2025-09-08 08:00:00');
