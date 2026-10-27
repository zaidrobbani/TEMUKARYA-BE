-- DDL TEMUKARYA (MySQL 8.4), hasil generate otomatis dari migrasi Alembic.
-- JANGAN diedit manual. Generate ulang setelah ada migrasi baru:
--   docker compose exec -T api alembic upgrade head --sql 2>/dev/null > docs/schema.sql

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> c34c4e3c9286

CREATE TABLE users (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    `role` VARCHAR(20) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

INSERT INTO alembic_version (version_num) VALUES ('c34c4e3c9286');

-- Running upgrade c34c4e3c9286 -> 3f9a1c7e2b40

ALTER TABLE users MODIFY id CHAR(36) NOT NULL DEFAULT (UUID());

UPDATE users SET id = UUID();

ALTER TABLE users MODIFY created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3);

ALTER TABLE users ADD COLUMN phone_number VARCHAR(20);

ALTER TABLE users ADD COLUMN profile_image_url VARCHAR(500);

ALTER TABLE users ADD COLUMN updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3);

CREATE TABLE umkm_profiles (
    user_id CHAR(36) NOT NULL, 
    business_name VARCHAR(160) NOT NULL, 
    business_category VARCHAR(100) NOT NULL, 
    business_address VARCHAR(300) NOT NULL, 
    city VARCHAR(100) NOT NULL, 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE freelancer_profiles (
    user_id CHAR(36) NOT NULL, 
    professional_title VARCHAR(150) NOT NULL, 
    bio TEXT, 
    city VARCHAR(100) NOT NULL, 
    service_price_min BIGINT UNSIGNED, 
    service_price_max BIGINT UNSIGNED, 
    availability_status VARCHAR(25) NOT NULL DEFAULT 'AVAILABLE', 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (user_id), 
    CONSTRAINT ck_freelancer_profiles_price_range CHECK (service_price_min IS NULL OR service_price_max IS NULL OR service_price_min <= service_price_max), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE skills (
    id VARCHAR(50) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

INSERT INTO skills (id, name) VALUES ('logo_design', 'Desain Logo');

INSERT INTO skills (id, name) VALUES ('brand_identity_design', 'Desain Identitas Merek');

INSERT INTO skills (id, name) VALUES ('packaging_design', 'Desain Kemasan & Label');

INSERT INTO skills (id, name) VALUES ('social_media_design', 'Desain Konten Media Sosial');

INSERT INTO skills (id, name) VALUES ('promotional_design', 'Desain Materi Promosi');

INSERT INTO skills (id, name) VALUES ('photography', 'Fotografi');

INSERT INTO skills (id, name) VALUES ('photo_editing', 'Editing Foto');

INSERT INTO skills (id, name) VALUES ('videography', 'Videografi');

INSERT INTO skills (id, name) VALUES ('video_editing', 'Editing Video');

INSERT INTO skills (id, name) VALUES ('motion_graphics', 'Motion Graphics');

INSERT INTO skills (id, name) VALUES ('voice_over', 'Voice Over');

INSERT INTO skills (id, name) VALUES ('copywriting', 'Copywriting');

INSERT INTO skills (id, name) VALUES ('product_description_writing', 'Penulisan Deskripsi Produk');

INSERT INTO skills (id, name) VALUES ('article_writing', 'Penulisan Artikel');

INSERT INTO skills (id, name) VALUES ('video_scriptwriting', 'Penulisan Naskah Video');

INSERT INTO skills (id, name) VALUES ('content_planning', 'Perencanaan Konten');

INSERT INTO skills (id, name) VALUES ('social_media_management', 'Pengelolaan Akun Media Sosial');

INSERT INTO skills (id, name) VALUES ('meta_ads', 'Pengelolaan Iklan Instagram & Facebook');

INSERT INTO skills (id, name) VALUES ('google_ads', 'Pengelolaan Google Ads');

INSERT INTO skills (id, name) VALUES ('seo', 'Optimasi Mesin Pencari (SEO)');

INSERT INTO skills (id, name) VALUES ('web_design', 'Desain Web');

INSERT INTO skills (id, name) VALUES ('web_programming', 'Pemrograman Web');

INSERT INTO skills (id, name) VALUES ('wordpress_development', 'Pembuatan Website WordPress');

INSERT INTO skills (id, name) VALUES ('website_maintenance', 'Pemeliharaan Website');

INSERT INTO skills (id, name) VALUES ('marketplace_setup', 'Penyiapan Toko Online');

INSERT INTO skills (id, name) VALUES ('marketplace_management', 'Pengelolaan Toko Online');

CREATE TABLE freelancer_skills (
    freelancer_id CHAR(36) NOT NULL, 
    skill_id VARCHAR(50) NOT NULL, 
    PRIMARY KEY (freelancer_id, skill_id), 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE RESTRICT
);

CREATE TABLE freelancer_experiences (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    freelancer_id CHAR(36) NOT NULL, 
    job_title VARCHAR(150) NOT NULL, 
    organization_name VARCHAR(160) NOT NULL, 
    description TEXT NOT NULL, 
    start_date DATE NOT NULL, 
    end_date DATE, 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_freelancer_experiences_date_range CHECK (end_date IS NULL OR end_date >= start_date), 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE CASCADE
);

CREATE TABLE portfolios (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    freelancer_id CHAR(36) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    description TEXT NOT NULL, 
    project_url VARCHAR(1000), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE CASCADE
);

CREATE TABLE portfolio_media (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    portfolio_id CHAR(36) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    mime_type VARCHAR(100) NOT NULL, 
    file_size_bytes BIGINT UNSIGNED NOT NULL, 
    uploaded_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    sort_order INTEGER UNSIGNED NOT NULL DEFAULT '0', 
    is_cover BOOL NOT NULL DEFAULT 0, 
    PRIMARY KEY (id), 
    FOREIGN KEY(portfolio_id) REFERENCES portfolios (id) ON DELETE CASCADE
);

UPDATE alembic_version SET version_num='3f9a1c7e2b40' WHERE alembic_version.version_num = 'c34c4e3c9286';

-- Running upgrade 3f9a1c7e2b40 -> 8d2e4b6a1c93

CREATE TABLE project_categories (
    id VARCHAR(50) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    description VARCHAR(400) NOT NULL, 
    is_active BOOL NOT NULL DEFAULT 1, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('website', 'Website', 'Pembuatan, desain, dan pemeliharaan website', true);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('graphic_design', 'Desain Grafis', 'Logo, identitas merek, kemasan, dan materi promosi', true);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('content_creation', 'Pembuatan Konten', 'Konten foto, video, dan tulisan untuk promosi', true);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('digital_marketing', 'Digital Marketing', 'Iklan berbayar, SEO, dan strategi pemasaran digital', true);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('social_media_management', 'Pengelolaan Media Sosial', 'Perencanaan dan pengelolaan akun media sosial', true);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('product_photography', 'Fotografi Produk', 'Foto dan video produk untuk katalog atau toko online', true);

INSERT INTO project_categories (id, name, description, is_active) VALUES ('other_technology', 'Teknologi Lainnya', 'Kebutuhan teknologi lain, misalnya penyiapan toko online', true);

CREATE TABLE projects (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    umkm_id CHAR(36) NOT NULL, 
    category_id VARCHAR(50) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    description TEXT NOT NULL, 
    budget BIGINT UNSIGNED NOT NULL, 
    deadline DATE NOT NULL, 
    status VARCHAR(40) NOT NULL DEFAULT 'TERBUKA', 
    published_at DATETIME(3), 
    started_at DATETIME(3), 
    completed_at DATETIME(3), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_projects_budget_positive CHECK (budget > 0), 
    FOREIGN KEY(umkm_id) REFERENCES umkm_profiles (user_id) ON DELETE RESTRICT, 
    FOREIGN KEY(category_id) REFERENCES project_categories (id) ON DELETE RESTRICT
);

CREATE INDEX ix_projects_status_published_at ON projects (status, published_at);

CREATE TABLE project_skills (
    project_id CHAR(36) NOT NULL, 
    skill_id VARCHAR(50) NOT NULL, 
    PRIMARY KEY (project_id, skill_id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE RESTRICT
);

CREATE TABLE project_attachments (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    original_file_name VARCHAR(255) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    mime_type VARCHAR(100) NOT NULL, 
    file_size_bytes BIGINT UNSIGNED NOT NULL, 
    uploaded_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE TABLE project_applications (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    freelancer_id CHAR(36) NOT NULL, 
    proposed_price BIGINT UNSIGNED NOT NULL, 
    estimated_duration_days INTEGER UNSIGNED NOT NULL, 
    proposal_message TEXT NOT NULL, 
    status VARCHAR(30) NOT NULL DEFAULT 'SUBMITTED', 
    submitted_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_project_applications_project_freelancer UNIQUE (project_id, freelancer_id), 
    CONSTRAINT ck_project_applications_price_positive CHECK (proposed_price > 0), 
    CONSTRAINT ck_project_applications_duration_positive CHECK (estimated_duration_days > 0), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE RESTRICT
);

UPDATE alembic_version SET version_num='8d2e4b6a1c93' WHERE alembic_version.version_num = '3f9a1c7e2b40';

-- Running upgrade 8d2e4b6a1c93 -> b7c1e9d3f582

CREATE TABLE project_agreements (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    freelancer_id CHAR(36) NOT NULL, 
    application_id CHAR(36), 
    selection_source VARCHAR(30) NOT NULL, 
    scope_of_work TEXT NOT NULL, 
    agreed_price BIGINT UNSIGNED NOT NULL, 
    agreed_deadline DATE NOT NULL, 
    status VARCHAR(35) NOT NULL DEFAULT 'PENDING_APPROVAL', 
    agreement_version INTEGER UNSIGNED NOT NULL DEFAULT '1', 
    umkm_approved_at DATETIME(3), 
    freelancer_approved_at DATETIME(3), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_project_agreements_project UNIQUE (project_id), 
    CONSTRAINT ck_project_agreements_price_positive CHECK (agreed_price > 0), 
    CONSTRAINT ck_project_agreements_application_source CHECK ((selection_source = 'APPLICATION') = (application_id IS NOT NULL)), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE RESTRICT, 
    FOREIGN KEY(application_id) REFERENCES project_applications (id) ON DELETE RESTRICT
);

CREATE TABLE project_milestones (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    description TEXT NOT NULL, 
    weight_percent NUMERIC(5, 2) NOT NULL, 
    status VARCHAR(25) NOT NULL DEFAULT 'BELUM_SELESAI', 
    sort_order INTEGER UNSIGNED NOT NULL, 
    completed_at DATETIME(3), 
    updated_by_user_id CHAR(36), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_project_milestones_project_order UNIQUE (project_id, sort_order), 
    CONSTRAINT ck_project_milestones_weight_range CHECK (weight_percent > 0 AND weight_percent <= 100), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, 
    FOREIGN KEY(updated_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE TABLE project_status_history (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    previous_status VARCHAR(40), 
    new_status VARCHAR(40) NOT NULL, 
    action VARCHAR(50) NOT NULL, 
    change_reason TEXT, 
    change_source VARCHAR(15) NOT NULL DEFAULT 'USER', 
    changed_by_user_id CHAR(36), 
    changed_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT, 
    FOREIGN KEY(changed_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_project_status_history_project_changed_at ON project_status_history (project_id, changed_at);

CREATE TABLE project_submissions (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    version_number INTEGER UNSIGNED NOT NULL, 
    submission_note TEXT, 
    result_url VARCHAR(1000), 
    submitted_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_project_submissions_project_version UNIQUE (project_id, version_number), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT
);

CREATE TABLE submission_files (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    submission_id CHAR(36) NOT NULL, 
    original_file_name VARCHAR(255) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    mime_type VARCHAR(100) NOT NULL, 
    file_size_bytes BIGINT UNSIGNED NOT NULL, 
    uploaded_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    FOREIGN KEY(submission_id) REFERENCES project_submissions (id) ON DELETE CASCADE
);

CREATE TABLE submission_reviews (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    submission_id CHAR(36) NOT NULL, 
    reviewer_user_id CHAR(36) NOT NULL, 
    decision VARCHAR(25) NOT NULL, 
    review_note TEXT, 
    reviewed_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_submission_reviews_submission UNIQUE (submission_id), 
    CONSTRAINT ck_submission_reviews_revision_note CHECK (decision <> 'REVISION_REQUESTED' OR (review_note IS NOT NULL AND review_note <> '')), 
    FOREIGN KEY(submission_id) REFERENCES project_submissions (id) ON DELETE RESTRICT, 
    FOREIGN KEY(reviewer_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE TABLE freelancer_reviews (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    project_id CHAR(36) NOT NULL, 
    rating TINYINT UNSIGNED NOT NULL, 
    review_text TEXT, 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_freelancer_reviews_project UNIQUE (project_id), 
    CONSTRAINT ck_freelancer_reviews_rating_range CHECK (rating BETWEEN 1 AND 5), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT
);

UPDATE alembic_version SET version_num='b7c1e9d3f582' WHERE alembic_version.version_num = '8d2e4b6a1c93';

-- Running upgrade b7c1e9d3f582 -> 1e5a7c9b3d26

CREATE TABLE conversations (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    umkm_id CHAR(36) NOT NULL, 
    freelancer_id CHAR(36) NOT NULL, 
    project_id CHAR(36), 
    project_key CHAR(36) GENERATED ALWAYS AS (coalesce(project_id, '')) STORED, 
    last_message_at DATETIME(3), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_conversations_participants_project UNIQUE (umkm_id, freelancer_id, project_key), 
    FOREIGN KEY(umkm_id) REFERENCES umkm_profiles (user_id) ON DELETE RESTRICT, 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE RESTRICT, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE RESTRICT
);

CREATE INDEX ix_conversations_umkm_last_message ON conversations (umkm_id, last_message_at);

CREATE INDEX ix_conversations_freelancer_last_message ON conversations (freelancer_id, last_message_at);

CREATE TABLE messages (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    conversation_id CHAR(36) NOT NULL, 
    sender_user_id CHAR(36) NOT NULL, 
    message_text TEXT, 
    message_type VARCHAR(20) NOT NULL DEFAULT 'TEXT', 
    sent_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    read_at DATETIME(3), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_messages_text_required CHECK (message_type <> 'TEXT' OR message_text IS NOT NULL), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(sender_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_messages_conversation_sent_at ON messages (conversation_id, sent_at);

CREATE TABLE message_attachments (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    message_id CHAR(36) NOT NULL, 
    original_file_name VARCHAR(255) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    mime_type VARCHAR(100) NOT NULL, 
    file_size_bytes BIGINT UNSIGNED NOT NULL, 
    uploaded_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    FOREIGN KEY(message_id) REFERENCES messages (id) ON DELETE CASCADE
);

CREATE TABLE notifications (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    user_id CHAR(36) NOT NULL, 
    notification_type VARCHAR(45) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    body TEXT NOT NULL, 
    reference_type VARCHAR(40), 
    reference_id CHAR(36), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    read_at DATETIME(3), 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_created_at ON notifications (user_id, created_at);

UPDATE alembic_version SET version_num='1e5a7c9b3d26' WHERE alembic_version.version_num = 'b7c1e9d3f582';

-- Running upgrade 1e5a7c9b3d26 -> c4f8a2d6e071

CREATE TABLE payments (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    agreement_id CHAR(36) NOT NULL, 
    gross_amount BIGINT UNSIGNED NOT NULL, 
    platform_fee_amount BIGINT UNSIGNED NOT NULL, 
    freelancer_amount BIGINT UNSIGNED NOT NULL, 
    payment_method VARCHAR(30) NOT NULL DEFAULT 'QRIS_SIMULATION', 
    status VARCHAR(20) NOT NULL DEFAULT 'MENUNGGU', 
    fund_status VARCHAR(20), 
    paid_at DATETIME(3), 
    released_at DATETIME(3), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_payments_agreement UNIQUE (agreement_id), 
    CONSTRAINT ck_payments_gross_positive CHECK (gross_amount > 0), 
    CONSTRAINT ck_payments_amount_split CHECK (platform_fee_amount + freelancer_amount = gross_amount), 
    CONSTRAINT ck_payments_fund_requires_paid CHECK (fund_status IS NULL OR status = 'BERHASIL'), 
    CONSTRAINT ck_payments_fund_status_values CHECK (fund_status IS NULL OR fund_status IN ('HELD', 'RELEASED')), 
    FOREIGN KEY(agreement_id) REFERENCES project_agreements (id) ON DELETE RESTRICT
);

CREATE TABLE payment_attempts (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    payment_id CHAR(36) NOT NULL, 
    attempt_number INTEGER UNSIGNED NOT NULL, 
    idempotency_key VARCHAR(64), 
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', 
    failure_reason VARCHAR(255), 
    attempted_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    completed_at DATETIME(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_payment_attempts_payment_number UNIQUE (payment_id, attempt_number), 
    CONSTRAINT uq_payment_attempts_idempotency_key UNIQUE (idempotency_key), 
    FOREIGN KEY(payment_id) REFERENCES payments (id) ON DELETE RESTRICT
);

CREATE TABLE wallets (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    freelancer_id CHAR(36) NOT NULL, 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_wallets_freelancer UNIQUE (freelancer_id), 
    FOREIGN KEY(freelancer_id) REFERENCES freelancer_profiles (user_id) ON DELETE RESTRICT
);

CREATE TABLE wallet_transactions (
    id CHAR(36) NOT NULL DEFAULT (UUID()), 
    wallet_id CHAR(36) NOT NULL, 
    payment_id CHAR(36) NOT NULL, 
    transaction_type VARCHAR(30) NOT NULL, 
    balance_type VARCHAR(20) NOT NULL, 
    amount_delta BIGINT NOT NULL, 
    description VARCHAR(400), 
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_wallet_transactions_payment_event UNIQUE (payment_id, transaction_type, balance_type), 
    CONSTRAINT ck_wallet_transactions_nonzero CHECK (amount_delta <> 0), 
    CONSTRAINT ck_wallet_transactions_balance_type CHECK (balance_type IN ('HELD', 'AVAILABLE')), 
    FOREIGN KEY(wallet_id) REFERENCES wallets (id) ON DELETE RESTRICT, 
    FOREIGN KEY(payment_id) REFERENCES payments (id) ON DELETE RESTRICT
);

CREATE INDEX ix_wallet_transactions_wallet_created_at ON wallet_transactions (wallet_id, created_at);

UPDATE alembic_version SET version_num='c4f8a2d6e071' WHERE alembic_version.version_num = '1e5a7c9b3d26';

