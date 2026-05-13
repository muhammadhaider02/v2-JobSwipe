'use client';

import { motion } from 'motion/react';
import { FormField } from './form-field';

interface StepCertificatesProps {
  certificates: {
    name: string;
    issuer: string;
    issueDate: string;
    expiryDate?: string;
  };
  onInput: (
    field: string,
  ) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring' as const, stiffness: 100, damping: 20 },
  },
};

export function StepCertificates({
  certificates,
  onInput,
}: StepCertificatesProps) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      <motion.div variants={item}>
        <FormField
          label="Certificate Name"
          id="cert-name"
          value={certificates.name}
          onChange={onInput('name')}
          placeholder="AWS Solutions Architect"
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="Issuer"
          id="cert-issuer"
          value={certificates.issuer}
          onChange={onInput('issuer')}
          placeholder="Amazon Web Services"
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="Issue Date"
          id="cert-issueDate"
          type="date"
          value={certificates.issueDate}
          onChange={onInput('issueDate')}
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="Expiry Date (optional)"
          id="cert-expiryDate"
          type="date"
          value={certificates.expiryDate || ''}
          onChange={onInput('expiryDate')}
        />
      </motion.div>
    </motion.div>
  );
}
