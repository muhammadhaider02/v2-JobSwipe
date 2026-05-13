'use client';

import { motion } from 'motion/react';
import { FormField } from './form-field';

interface StepProfileProps {
  profile: {
    name: string;
    email: string;
    phone: string;
    location: string;
    summary: string;
    github: string;
    linkedin: string;
    portfolio: string;
  };
  errors: Record<string, string>;
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

export function StepProfile({ profile, errors, onInput }: StepProfileProps) {
  return (
    <motion.div
      variants={stagger}
      initial="hidden"
      animate="show"
      className="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      <motion.div variants={item}>
        <FormField
          label="Name"
          id="profile-name"
          required
          value={profile.name}
          onChange={onInput('name')}
          error={errors.name}
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="Email"
          id="profile-email"
          type="email"
          required
          value={profile.email}
          onChange={onInput('email')}
          error={errors.email}
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="Phone"
          id="profile-phone"
          type="tel"
          value={profile.phone}
          onChange={onInput('phone')}
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="Location"
          id="profile-location"
          value={profile.location}
          onChange={onInput('location')}
        />
      </motion.div>
      <motion.div variants={item} className="md:col-span-2">
        <FormField
          label="Summary"
          id="profile-summary"
          multiline
          value={profile.summary}
          onChange={onInput('summary')}
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="GitHub"
          id="profile-github"
          value={profile.github}
          onChange={onInput('github')}
          placeholder="https://github.com/username"
        />
      </motion.div>
      <motion.div variants={item}>
        <FormField
          label="LinkedIn"
          id="profile-linkedin"
          value={profile.linkedin}
          onChange={onInput('linkedin')}
          placeholder="https://linkedin.com/in/username"
        />
      </motion.div>
      <motion.div variants={item} className="md:col-span-2">
        <FormField
          label="Portfolio"
          id="profile-portfolio"
          value={profile.portfolio}
          onChange={onInput('portfolio')}
          placeholder="https://yoursite.com"
        />
      </motion.div>
    </motion.div>
  );
}
